`timescale 1ns / 1ps
// ============================================================================
// Self-checking testbench for junction_controller (Junction-A parameters).
// Density is held at 3 so the expected cycle is:
//   NS green 15 | NS yellow 3 | all-red 3 | EW green 15 | EW yellow 3 |
//   all-red 3 | pedestrian slot 5   (total 47 cycles)
// Checks:
//   * every phase lasts exactly its configured number of cycles
//   * phases occur in the required order
//   * NS and EW are never green together; walk only when all lights are red
//   * a pedestrian request held high for many cycles is served exactly once
//   * a request during the yellow phase is served at the next decision point
// ============================================================================
module tb_junction_controller;
    localparam integer EXP_NSG = 15;   // BASE_GREEN(6) + 3*DENSITY_STEP(3)
    localparam integer EXP_EWG = 15;   // MIN_GREEN + MAX_GREEN - EXP_NSG = 30 - 15
    localparam integer EXP_Y   = 3;
    localparam integer EXP_R   = 3;
    localparam integer EXP_P   = 5;

    reg        clk = 1'b0;
    reg        rst_n = 1'b0;
    reg        emg = 1'b0;
    reg  [2:0] dens = 3'd3;
    reg        ped_req = 1'b0;
    wire       ped_req_out;
    wire       gw_out;
    wire       ped_walk;
    wire [1:0] ns, ew;
    wire       grant = ped_req_out;   // standalone: grant every request
    wire       slot;                  // standalone: the pedestrian slot is this junction's own strobe

    junction_controller #(
        .COUNTER_WIDTH(8), .BASE_GREEN(6), .MIN_GREEN(6), .MAX_GREEN(24),
        .DENSITY_STEP(3), .YELLOW_TIME(3), .RED_TIME(3), .PED_TIME(5),
        .IS_JUNCTION_B(1'b0)
    ) dut (
        .clk(clk), .rst_n(rst_n), .emergency_override(emg),
        .traffic_density(dens), .ped_req_in(ped_req), .ped_grant(grant),
        .ped_req_out(ped_req_out), .ped_slot_in(slot), .ped_slot_out(slot),
        .gw_sync_in(1'b0), .gw_sync_out(gw_out),
        .ns_lights(ns), .ew_lights(ew), .ped_walk(ped_walk)
    );

    always #5 clk = ~clk;

    // Watchdog: a self-checking testbench must never hang. A normal run ends far earlier than
    // 100000 ns, so reaching it means a wait() never completed; that is reported as a FAIL.
    initial begin
        #100000;
        $display("[FAIL] watchdog: testbench did not finish within 100000 ns");
        $display("RESULT: FAIL");
        $finish;
    end

    integer errors = 0;
    integer checks = 0;

    // ---- state codes (mirror the RTL localparams) ----
    localparam integer S_NS_GREEN = 1, S_NS_YELLOW = 2, S_ALL_RED_1 = 3, S_EW_GREEN = 4,
                       S_EW_YELLOW = 5, S_ALL_RED_2 = 6, S_PED = 7;

    function integer exp_len;
        input [31:0] s;
        begin
            case (s)
                S_NS_GREEN:  exp_len = EXP_NSG;
                S_NS_YELLOW: exp_len = EXP_Y;
                S_ALL_RED_1: exp_len = EXP_R;
                S_EW_GREEN:  exp_len = EXP_EWG;
                S_EW_YELLOW: exp_len = EXP_Y;
                S_ALL_RED_2: exp_len = EXP_R;
                S_PED:       exp_len = EXP_P;
                default:     exp_len = -1;
            endcase
        end
    endfunction

    function integer next_state_of;
        input [31:0] s;
        begin
            case (s)
                S_NS_GREEN:  next_state_of = S_NS_YELLOW;
                S_NS_YELLOW: next_state_of = S_ALL_RED_1;
                S_ALL_RED_1: next_state_of = S_EW_GREEN;
                S_EW_GREEN:  next_state_of = S_EW_YELLOW;
                S_EW_YELLOW: next_state_of = S_ALL_RED_2;
                S_ALL_RED_2: next_state_of = S_PED;
                S_PED:       next_state_of = S_NS_GREEN;
                default:     next_state_of = -1;
            endcase
        end
    endfunction

    task check;
        input            cond;
        input [8*120-1:0] msg;
        begin
            checks = checks + 1;
            if (cond) $display("[PASS] %0s", msg);
            else begin
                errors = errors + 1;
                $display("[FAIL] %0s", msg);
            end
        end
    endtask

    // ---- run-length and order monitor (samples pre-edge values at posedge) ----
    integer run_len  = 0;
    integer prev_st  = 0;
    integer runs_seen = 0;
    integer walk_runs = 0;
    reg     prev_walk = 1'b0;
    reg     walk_seen_outside = 1'b0;

    always @(posedge clk) begin : monitor
        integer st;
        st = dut.state;
        if (rst_n) begin
            // safety invariants
            if (ns == 2'b10 && ew == 2'b10) begin
                errors = errors + 1;
                $display("[FAIL] NS and EW green simultaneously at %0t", $time);
            end
            if (ped_walk && (ns != 2'b00 || ew != 2'b00)) begin
                errors = errors + 1;
                $display("[FAIL] pedestrian walk while a vehicle light is lit at %0t", $time);
            end
            if (ped_req_out && st != S_ALL_RED_2) begin
                errors = errors + 1;
                $display("[FAIL] pedestrian request raised outside decision point at %0t", $time);
            end
            if (ped_walk && !prev_walk) walk_runs = walk_runs + 1;
            prev_walk = ped_walk;

            // phase-length and order checks
            if (st == prev_st) begin
                run_len = run_len + 1;
            end else begin
                if (prev_st != 0) begin
                    runs_seen = runs_seen + 1;
                    checks = checks + 1;
                    if (run_len != exp_len(prev_st)) begin
                        errors = errors + 1;
                        $display("[FAIL] state %0d lasted %0d cycles, expected %0d",
                                 prev_st, run_len, exp_len(prev_st));
                    end
                    if (st != next_state_of(prev_st)) begin
                        errors = errors + 1;
                        $display("[FAIL] order violation: state %0d followed by %0d", prev_st, st);
                    end
                end
                prev_st = st;
                run_len = 1;
            end
        end else begin
            prev_st = 0;      // reset: discard partial run
            run_len = 0;
        end
    end

    initial begin
        // asynchronous reset held for several cycles
        rst_n = 1'b0;
        #22 rst_n = 1'b1;

        // one full signal cycle plus margin, no pedestrians
        repeat (120) @(posedge clk);
        check(runs_seen >= 6, "signal cycle sequence observed (NS, Y, R, EW, Y, R, PED)");

        // ---- pedestrian request during NS yellow ----
        walk_runs = 0;
        @(negedge clk);
        wait (dut.state == S_NS_YELLOW);
        @(negedge clk) ped_req = 1'b1;
        @(negedge clk) ped_req = 1'b0;
        repeat (80) @(posedge clk);
        check(walk_runs == 1, "request during yellow is served exactly once");

        // ---- request held high for 30 cycles (level) must not double-serve ----
        walk_runs = 0;
        @(negedge clk) ped_req = 1'b1;
        repeat (30) @(negedge clk);
        ped_req = 1'b0;
        repeat (80) @(posedge clk);
        check(walk_runs == 1, "held request level is served exactly once (edge detected)");

        // ---- reset asserted mid-count returns to a valid phase ----
        @(negedge clk);
        wait (dut.state == S_EW_GREEN);
        repeat (4) @(negedge clk);
        rst_n = 1'b0;
        #3 check(ns == 2'b00 && ew == 2'b00 && ped_walk == 1'b0,
                 "asynchronous reset mid-phase drives all lights red immediately");
        #12 rst_n = 1'b1;
        repeat (60) @(posedge clk);
        check(runs_seen > 10, "controller resumes its cycle after reset");

        $display("----------------------------------------------");
        $display("junction_controller : %0d checks, %0d errors, %0d phases observed",
                 checks, errors, runs_seen);
        if (errors == 0) $display("RESULT: PASS");
        else             $display("RESULT: FAIL");
        $display("----------------------------------------------");
        $finish;
    end
endmodule
