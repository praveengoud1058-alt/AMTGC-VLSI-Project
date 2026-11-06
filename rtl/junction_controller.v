`timescale 1ns / 1ps
// ============================================================================
// junction_controller
//   Moore FSM controlling one 4-way junction. Instantiated twice in amtgc_top
//   (Junction A and Junction B) with different parameter values.
//
//   Signal cycle (fixed length, see docs/architecture_final.md):
//     NS_GREEN -> NS_YELLOW -> ALL_RED_1 -> EW_GREEN -> EW_YELLOW -> ALL_RED_2
//     -> PED (pedestrian slot, always PED_TIME cycles) -> NS_GREEN ...
//   NS_GREEN + EW_GREEN always equals MIN_GREEN + MAX_GREEN, so the density
//   only changes the NS/EW split, never the cycle length. This keeps the
//   green-wave offset exact for every density combination.
//
//   Phase durations are exact: a phase of D cycles is realised by loading the
//   timer with (D - TIMER_OVERHEAD). Each phase starts with one entry cycle in
//   which the timer is held in reset (start low) and its stale 'done' is masked.
//   Minimum phase length is 3 cycles.
// ============================================================================
module junction_controller #(
    parameter COUNTER_WIDTH = 8,
    parameter BASE_GREEN    = 6,    // NS green (cycles) at traffic_density = 0
    parameter MIN_GREEN     = 6,    // lower clamp for NS and EW green
    parameter MAX_GREEN     = 24,   // upper clamp for NS and EW green
    parameter DENSITY_STEP  = 3,    // extra NS green cycles per density level
    parameter YELLOW_TIME   = 3,
    parameter RED_TIME      = 3,    // all-red safety interval
    parameter PED_TIME      = 5,    // pedestrian slot length (fixed every cycle)
    parameter IS_JUNCTION_B = 1'b0  // 1: waits for green-wave pulse after reset/emergency
)(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 emergency_override,
    input  wire [2:0]           traffic_density,
    input  wire                 ped_req_in,     // pedestrian button (level, edge-detected here)
    input  wire                 ped_grant,      // from ped_arbiter
    output wire                 ped_req_out,    // to ped_arbiter (high only during a pedestrian slot)
    input  wire                 ped_slot_in,    // shared pedestrian slot strobe (from amtgc_top)
    output wire                 ped_slot_out,   // this junction's own decision strobe (end of ALL_RED_2)
    input  wire                 gw_sync_in,     // green-wave pulse (Junction B only)
    output wire                 gw_sync_out,    // green-wave pulse at NS green entry (Junction A)
    output reg  [1:0]           ns_lights,      // 00 red, 01 yellow, 10 green
    output reg  [1:0]           ew_lights,
    output reg                  ped_walk
);

    // ---------------- state encoding ----------------
    localparam [3:0] S_GW_WAIT   = 4'd0;   // Junction B only: wait for green-wave pulse
    localparam [3:0] S_NS_GREEN  = 4'd1;
    localparam [3:0] S_NS_YELLOW = 4'd2;
    localparam [3:0] S_ALL_RED_1 = 4'd3;
    localparam [3:0] S_EW_GREEN  = 4'd4;
    localparam [3:0] S_EW_YELLOW = 4'd5;
    localparam [3:0] S_ALL_RED_2 = 4'd6;
    localparam [3:0] S_PED       = 4'd7;
    localparam [3:0] S_EMERGENCY = 4'd8;

    localparam [1:0] LIGHT_RED    = 2'b00;
    localparam [1:0] LIGHT_YELLOW = 2'b01;
    localparam [1:0] LIGHT_GREEN  = 2'b10;

    localparam integer TIMER_OVERHEAD  = 2;                     // entry cycle + timer latency
    localparam integer MIN_TIMER_TARGET = 1;                    // smallest legal count_target (phases >= 3 cycles)
    localparam integer CYCLE_GREEN_SUM = MIN_GREEN + MAX_GREEN; // NS + EW green is constant
    localparam [3:0]   RESUME_STATE    = IS_JUNCTION_B ? S_GW_WAIT : S_ALL_RED_1;

    // ---------------- functions ----------------
    // Convert a phase duration (cycles) into a timer count_target.
    function [31:0] to_timer_target;
        input [31:0] duration;
        begin
            if (duration > TIMER_OVERHEAD)
                to_timer_target = duration - TIMER_OVERHEAD;
            else
                to_timer_target = MIN_TIMER_TARGET;
        end
    endfunction

    // NS green duration for a density level, clamped to [MIN_GREEN, MAX_GREEN].
    function [31:0] ns_green_dur;
        input [2:0] density;
        reg   [31:0] t;
        begin
            t = BASE_GREEN + density * DENSITY_STEP;
            if (t < MIN_GREEN)
                ns_green_dur = MIN_GREEN;
            else if (t > MAX_GREEN)
                ns_green_dur = MAX_GREEN;
            else
                ns_green_dur = t;
        end
    endfunction

    // ---------------- registers / wires ----------------
    reg  [3:0]               state;
    reg  [3:0]               next_state;
    reg                      phase_entry;     // 1 during the first cycle of every phase
    reg  [2:0]               latched_density; // sampled once per signal cycle (at NS green entry)
    reg                      ped_pending;     // a pedestrian request is waiting
    reg                      ped_req_prev;    // previous ped_req_in, for edge detection
    reg                      ped_serve;       // this PED slot carries a walk
    reg                      timer_run;
    reg  [COUNTER_WIDTH-1:0] timer_target;

    wire                     timer_start;
    wire                     timer_done;
    wire [COUNTER_WIDTH-1:0] timer_count;
    wire                     tdone;
    wire                     decision;
    wire                     armed;
    wire [31:0]              ns_dur = ns_green_dur(latched_density);
    wire [31:0]              ew_dur = CYCLE_GREEN_SUM - ns_dur;

    assign timer_start = timer_run & ~phase_entry;
    assign tdone       = timer_done & ~phase_entry;   // ignore stale 'done' in entry cycle
    assign decision    = (state == S_ALL_RED_2) & tdone & ~emergency_override;

    // Pedestrian slot: the leader (Junction A) raises ped_slot_out once per signal cycle.
    // amtgc_top distributes it to both junctions, so both present their requests to the
    // arbiter in the SAME clock cycle. A junction takes part only while 'armed', i.e. while
    // its next PED slot is the one this strobe is deciding (EW_GREEN .. ALL_RED_2).
    assign armed        = (state == S_EW_GREEN) | (state == S_EW_YELLOW) | (state == S_ALL_RED_2);
    assign ped_slot_out = decision;
    assign ped_req_out  = ped_slot_in & armed & ped_pending & ~ped_serve & ~emergency_override;
    assign gw_sync_out = (state == S_NS_GREEN) & phase_entry;

    // ---------------- timer (reused, unmodified) ----------------
    generic_timer #(.COUNTER_WIDTH(COUNTER_WIDTH)) u_timer (
        .clk          (clk),
        .rst_n        (rst_n),
        .start        (timer_start),
        .count_target (timer_target),
        .done         (timer_done),
        .current_count(timer_count)
    );

    // ---------------- timer target per phase ----------------
    always @(*) begin
        timer_run    = 1'b0;
        timer_target = {COUNTER_WIDTH{1'b0}};
        case (state)
            S_NS_GREEN: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(ns_dur);
            end
            S_NS_YELLOW: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(YELLOW_TIME);
            end
            S_ALL_RED_1: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(RED_TIME);
            end
            S_EW_GREEN: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(ew_dur);
            end
            S_EW_YELLOW: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(YELLOW_TIME);
            end
            S_ALL_RED_2: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(RED_TIME);
            end
            S_PED: begin
                timer_run    = 1'b1;
                timer_target = to_timer_target(PED_TIME);
            end
            default: begin
                timer_run    = 1'b0;
                timer_target = {COUNTER_WIDTH{1'b0}};
            end
        endcase
    end

    // ---------------- next-state logic ----------------
    always @(*) begin
        next_state = state;
        if (emergency_override) begin
            next_state = S_EMERGENCY;             // 1-cycle latency to all-red
        end else begin
            case (state)
                S_GW_WAIT:   if (gw_sync_in) next_state = S_NS_GREEN;
                S_NS_GREEN:  if (tdone)      next_state = S_NS_YELLOW;
                S_NS_YELLOW: if (tdone)      next_state = S_ALL_RED_1;
                S_ALL_RED_1: if (tdone)      next_state = S_EW_GREEN;
                S_EW_GREEN:  if (tdone)      next_state = S_EW_YELLOW;
                S_EW_YELLOW: if (tdone)      next_state = S_ALL_RED_2;
                S_ALL_RED_2: if (tdone)      next_state = S_PED;
                S_PED:       if (tdone)      next_state = S_NS_GREEN;
                S_EMERGENCY:                 next_state = RESUME_STATE;
                default:                     next_state = RESUME_STATE; // invalid state -> safe all-red
            endcase
        end
    end

    // ---------------- sequential logic (non-blocking) ----------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= IS_JUNCTION_B ? S_GW_WAIT : S_NS_GREEN;
            phase_entry     <= 1'b1;
            latched_density <= 3'd0;
            ped_pending     <= 1'b0;
            ped_req_prev    <= 1'b0;
            ped_serve       <= 1'b0;
        end else begin
            state       <= next_state;
            phase_entry <= (next_state != state);

            // density sampled once at NS green entry and held for the whole cycle
            if (phase_entry && (state == S_NS_GREEN))
                latched_density <= traffic_density;

            // pedestrian request: edge-detected, latched until served, never lost or doubled
            ped_req_prev <= ped_req_in;
            if (ped_req_in && !ped_req_prev)
                ped_pending <= 1'b1;               // a new request wins over a serve in the same cycle
            else if (ped_req_out && ped_grant)
                ped_pending <= 1'b0;

            // walk is granted for this junction's next PED slot; cleared when that slot ends
            if (ped_req_out && ped_grant)
                ped_serve <= 1'b1;
            else if (state == S_PED && next_state != S_PED)
                ped_serve <= 1'b0;
        end
    end

    // ---------------- Moore outputs (combinational, default-assigned) ----------------
    // Outputs are forced to all-red while rst_n is asserted (immediate, no clock needed).
    always @(*) begin
        ns_lights = LIGHT_RED;
        ew_lights = LIGHT_RED;
        ped_walk  = 1'b0;
        if (rst_n) begin
            case (state)
                S_NS_GREEN:  ns_lights = LIGHT_GREEN;
                S_NS_YELLOW: ns_lights = LIGHT_YELLOW;
                S_EW_GREEN:  ew_lights = LIGHT_GREEN;
                S_EW_YELLOW: ew_lights = LIGHT_YELLOW;
                S_PED:       ped_walk  = ped_serve;
                default: begin
                    ns_lights = LIGHT_RED;
                    ew_lights = LIGHT_RED;
                    ped_walk  = 1'b0;
                end
            endcase
        end
    end

endmodule
