`timescale 1ns / 1ps
// ============================================================================
// amtgc_top : Adaptive Multi-Junction Traffic Grid Controller
//   - Two junction_controller instances (A = leader, B = follower) with
//     different density response (BASE_GREEN, DENSITY_STEP).
//   - One shared ped_arbiter (request/grant handshake only).
//   - Green-wave link: A's NS-green entry pulse is delayed by GW_DELAY_CYCLES
//     and used as B's start trigger. Measured offset: B NS entry - A NS entry
//     = GW_DELAY_CYCLES cycles (exact, verified in tb_amtgc_top).
//   - Reset: asynchronous assertion, synchronous de-assertion through a
//     2-flop synchroniser (matches docs/assumptions.md).
//   - emergency_override: both junctions enter all-red 1 clock cycle after
//     the override is sampled high, and resume from ALL_RED only after release.
//   - Pedestrian slot: Junction A's decision strobe (end of ALL_RED_2) is distributed to
//     both junctions, so both present their pending requests to the shared arbiter in the
//     same clock cycle. The arbiter serves one walk per slot, round-robin on contests.
// Constraints: MIN_GREEN, MAX_GREEN, YELLOW_TIME, RED_TIME, PED_TIME must be
// identical for both junctions (cycle length must match for the green wave).
// GW_DELAY_CYCLES must not exceed YELLOW_TIME + RED_TIME + MIN_GREEN (the pedestrian
// slot must reach Junction B while it is in EW_GREEN, EW_YELLOW or ALL_RED_2).
// ============================================================================
module amtgc_top #(
    parameter COUNTER_WIDTH   = 8,
    parameter GW_DELAY_CYCLES = 4         // green-wave offset in clock cycles (must be >= 2)
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       emergency_override,
    input  wire [2:0] density_a,
    input  wire [2:0] density_b,
    input  wire       ped_req_a,
    input  wire       ped_req_b,
    output wire [1:0] ns_lights_a,
    output wire [1:0] ew_lights_a,
    output wire       ped_walk_a,
    output wire [1:0] ns_lights_b,
    output wire [1:0] ew_lights_b,
    output wire       ped_walk_b
);

    // ---------------- reset synchroniser ----------------
    reg  [1:0] rst_sync;
    wire       rst_n_sync = rst_sync[1];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rst_sync <= 2'b00;
        else
            rst_sync <= {rst_sync[0], 1'b1};
    end

    // ---------------- green-wave delay line ----------------
    localparam integer GW_SR_W = GW_DELAY_CYCLES - 1;
    reg  [GW_SR_W-1:0] gw_sr;
    wire               gw_sync_a;
    wire               gw_sync_b_in = gw_sr[GW_DELAY_CYCLES-2];

    always @(posedge clk or negedge rst_n_sync) begin
        if (!rst_n_sync)
            gw_sr <= {GW_SR_W{1'b0}};
        else if (emergency_override)
            gw_sr <= {GW_SR_W{1'b0}};
        else
            gw_sr <= (gw_sr << 1) | gw_sync_a;
    end

    // ---------------- shared pedestrian arbiter ----------------
    wire ped_req_latch_a, ped_req_latch_b;
    wire ped_grant_a, ped_grant_b;
    wire ped_slot;                       // shared pedestrian slot strobe (from the leader)

    ped_arbiter u_ped_arbiter (
        .clk     (clk),
        .rst_n   (rst_n_sync),
        .req_a   (ped_req_latch_a),
        .req_b   (ped_req_latch_b),
        .grant_a (ped_grant_a),
        .grant_b (ped_grant_b)
    );

    // ---------------- Junction A (leader) ----------------
    junction_controller #(
        .COUNTER_WIDTH  (COUNTER_WIDTH),
        .BASE_GREEN     (6),
        .MIN_GREEN      (6),
        .MAX_GREEN      (24),
        .DENSITY_STEP   (3),
        .YELLOW_TIME    (3),
        .RED_TIME       (3),
        .PED_TIME       (5),
        .IS_JUNCTION_B  (1'b0)
    ) u_junction_a (
        .clk                (clk),
        .rst_n              (rst_n_sync),
        .emergency_override (emergency_override),
        .traffic_density    (density_a),
        .ped_req_in         (ped_req_a),
        .ped_grant          (ped_grant_a),
        .ped_req_out        (ped_req_latch_a),
        .ped_slot_in        (ped_slot),
        .ped_slot_out       (ped_slot),
        .gw_sync_in         (1'b0),
        .gw_sync_out        (gw_sync_a),
        .ns_lights          (ns_lights_a),
        .ew_lights          (ew_lights_a),
        .ped_walk           (ped_walk_a)
    );

    // ---------------- Junction B (follower, different density response) ----------------
    junction_controller #(
        .COUNTER_WIDTH  (COUNTER_WIDTH),
        .BASE_GREEN     (9),
        .MIN_GREEN      (6),
        .MAX_GREEN      (24),
        .DENSITY_STEP   (2),
        .YELLOW_TIME    (3),
        .RED_TIME       (3),
        .PED_TIME       (5),
        .IS_JUNCTION_B  (1'b1)
    ) u_junction_b (
        .clk                (clk),
        .rst_n              (rst_n_sync),
        .emergency_override (emergency_override),
        .traffic_density    (density_b),
        .ped_req_in         (ped_req_b),
        .ped_grant          (ped_grant_b),
        .ped_req_out        (ped_req_latch_b),
        .ped_slot_in        (ped_slot),
        .ped_slot_out       (),
        .gw_sync_in         (gw_sync_b_in),
        .gw_sync_out        (),
        .ns_lights          (ns_lights_b),
        .ew_lights          (ew_lights_b),
        .ped_walk           (ped_walk_b)
    );

endmodule
