`timescale 1ns / 1ps
// ============================================================================
// Unified self-checking system testbench for amtgc_top (Tasks 3, 4 and 5).
// Every check prints [PASS] or [FAIL]; RESULT line gives the final verdict.
//
// Automatic monitors (run every clock cycle):
//   M1 phase length: every phase lasts the configured number of cycles, using the
//      density latched at NS-green entry for both junctions
//   M2 phase order: GW_WAIT/NS/Y/R/EW/Y/R/PED sequence respected
//   M3 safety: never NS-green and EW-green together; walk only when all red
//   M4 emergency: override high in cycle t => both junctions all-red at cycle t+1
//   M5 green wave: every Junction-B NS-green entry is preceded by a Junction-A
//      NS-green entry exactly GW_DELAY_CYCLES earlier
//   M6 pedestrians: each request that finds nothing pending yields exactly one walk
//   M7 arbitration: the two grants are never active together (one walk per slot)
//   S4/S8 contested slots: for every simultaneous pair the two walks go to different junctions
//      and the junction served FIRST alternates from pair to pair (round-robin fairness)
// Directed scenarios: normal run, density sweep, pedestrian cases, fairness,
// emergency from every phase of each junction, mid-run reset, and a
// 20 000-cycle constrained-random run.
// ============================================================================
module tb_amtgc_top;
    localparam integer GW_D = 4;

    reg        clk = 1'b0;
    reg        rst_n = 1'b0;
    reg        emg = 1'b0;
    reg  [2:0] da = 3'd3;
    reg  [2:0] db = 3'd3;
    reg        pra = 1'b0;
    reg        prb = 1'b0;
    wire [1:0] nsA, ewA, nsB, ewB;
    wire       wA, wB;

    amtgc_top #(.COUNTER_WIDTH(8), .GW_DELAY_CYCLES(GW_D)) uut (
        .clk(clk), .rst_n(rst_n), .emergency_override(emg),
        .density_a(da), .density_b(db), .ped_req_a(pra), .ped_req_b(prb),
        .ns_lights_a(nsA), .ew_lights_a(ewA), .ped_walk_a(wA),
        .ns_lights_b(nsB), .ew_lights_b(ewB), .ped_walk_b(wB)
    );

    always #5 clk = ~clk;

    // Watchdog: a self-checking testbench must never hang. A normal run ends far earlier than
    // 1000000 ns, so reaching it means a wait() never completed; that is reported as a FAIL.
    initial begin
        #1000000;
        $display("[FAIL] watchdog: testbench did not finish within 1000000 ns");
        $display("RESULT: FAIL");
        $finish;
    end

    // ------------------------------------------------------------------
    integer errors = 0;
    integer checks = 0;
    integer inv_cycles = 0;
    integer offset_checks = 0;

    integer n_walk_a = 0, n_walk_b = 0;
    integer n_walks_total = 0;
    reg [1:0] walk_log [0:4095];      // 1 = walk started by A, 2 = walk started by B, in time order
    integer n_new_a = 0,  n_new_b = 0;
    integer rl [0:1];
    integer ps [0:1];
    integer expns [0:1];
    reg [3:0] rawst [0:1];
    reg [7:0] ahist = 8'd0;
    reg emg_d = 1'b0, pra_d = 1'b0, prb_d = 1'b0, wA_d = 1'b0, wB_d = 1'b0;

    function integer nsd;
        input [31:0] jj;
        input [31:0] d;
        integer t;
        begin
            if (jj == 0) t = 6 + 3 * d;
            else         t = 9 + 2 * d;
            if (t < 6)       nsd = 6;
            else if (t > 24) nsd = 24;
            else             nsd = t;
        end
    endfunction

    function integer exp_len;
        input [31:0] jj;
        input [31:0] s;
        begin
            case (s)
                1: exp_len = expns[jj];
                2: exp_len = 3;
                3: exp_len = 3;
                4: exp_len = 30 - expns[jj];
                5: exp_len = 3;
                6: exp_len = 3;
                7: exp_len = 5;
                default: exp_len = -1;
            endcase
        end
    endfunction

    function integer next_s;
        input [31:0] s;
        begin
            case (s)
                1: next_s = 2;
                2: next_s = 3;
                3: next_s = 4;
                4: next_s = 5;
                5: next_s = 6;
                6: next_s = 7;
                7: next_s = 1;
                default: next_s = -1;
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
                $display("[FAIL] %0s  (t=%0t)", msg, $time);
            end
        end
    endtask

    task wait_cycles;
        input integer n;
        begin
            repeat (n) @(negedge clk);
        end
    endtask

    // ------------------------------------------------------------------
    // Automatic monitors
    // ------------------------------------------------------------------
    always @(posedge clk) begin : monitors
        integer jj;
        reg [3:0] st;
        reg valid;
        reg [1:0] nsl, ewl;
        reg       wk;

        // M5 green wave: B NS entry must match A NS entry GW_D cycles earlier
        if (rst_n && uut.rst_n_sync && uut.u_junction_b.phase_entry &&
            (uut.u_junction_b.state == 4'd1)) begin
            offset_checks = offset_checks + 1;
            if (!ahist[GW_D-1]) begin
                errors = errors + 1;
                $display("[FAIL] green wave: B NS entry not %0d cycles after A NS entry (t=%0t)", GW_D, $time);
            end
        end
        ahist = {ahist[6:0], uut.gw_sync_a};

        if (uut.rst_n_sync) begin
            inv_cycles = inv_cycles + 1;
            // M3 safety
            if (nsA == 2'b10 && ewA == 2'b10) begin
                errors = errors + 1; $display("[FAIL] A: NS and EW green together (t=%0t)", $time);
            end
            if (nsB == 2'b10 && ewB == 2'b10) begin
                errors = errors + 1; $display("[FAIL] B: NS and EW green together (t=%0t)", $time);
            end
            if (wA && (nsA != 2'b00 || ewA != 2'b00)) begin
                errors = errors + 1; $display("[FAIL] A: walk while vehicles green (t=%0t)", $time);
            end
            if (wB && (nsB != 2'b00 || ewB != 2'b00)) begin
                errors = errors + 1; $display("[FAIL] B: walk while vehicles green (t=%0t)", $time);
            end
            // M4 emergency latency: override seen last cycle => all red now
            if (emg_d && (nsA != 2'b00 || ewA != 2'b00 || nsB != 2'b00 || ewB != 2'b00)) begin
                errors = errors + 1; $display("[FAIL] emergency: lights not all red one cycle after override (t=%0t)", $time);
            end
            // M6 pedestrian accounting
            if (pra && !pra_d &&
                (uut.u_junction_a.ped_pending == 1'b0 ||
                 (uut.u_junction_a.ped_req_out && uut.ped_grant_a)))
                n_new_a = n_new_a + 1;
            if (prb && !prb_d &&
                (uut.u_junction_b.ped_pending == 1'b0 ||
                 (uut.u_junction_b.ped_req_out && uut.ped_grant_b)))
                n_new_b = n_new_b + 1;
        end
        if (rst_n && uut.rst_n_sync && wA && !wA_d) begin
            n_walk_a = n_walk_a + 1;
            walk_log[n_walks_total] = 2'd1;
            n_walks_total = n_walks_total + 1;
        end
        if (rst_n && uut.rst_n_sync && wB && !wB_d) begin
            n_walk_b = n_walk_b + 1;
            walk_log[n_walks_total] = 2'd2;
            n_walks_total = n_walks_total + 1;
        end
        // M7 arbitration exclusivity: one walk per slot
        if (uut.rst_n_sync && uut.ped_grant_a && uut.ped_grant_b) begin
            errors = errors + 1;
            $display("[FAIL] arbiter granted both junctions in the same cycle (t=%0t)", $time);
        end
        wA_d = wA; wB_d = wB;
        emg_d = emg; pra_d = pra; prb_d = prb;

        // M1 / M2 phase length and order, per junction
        for (jj = 0; jj < 2; jj = jj + 1) begin
            st = (jj == 0) ? uut.u_junction_a.state : uut.u_junction_b.state;
            // record every NS-green entry (even one cut short by an override): the design
            // latches density on that entry edge, so later EW lengths depend on it
            if (!uut.rst_n_sync) begin
                rawst[jj] = 0;
            end else begin
                if (st == 4'd1 && rawst[jj] != 4'd1)
                    expns[jj] = nsd(jj, (jj == 0) ? da : db);
                rawst[jj] = st;
            end
            valid = uut.rst_n_sync && !emg && (st != 4'd8) && (st != 4'd0);
            if (!valid) begin
                ps[jj] = 0;
                rl[jj] = 0;
            end else if (st == ps[jj]) begin
                rl[jj] = rl[jj] + 1;
            end else begin
                if (ps[jj] != 0) begin
                    checks = checks + 1;
                    if (rl[jj] != exp_len(jj, ps[jj])) begin
                        errors = errors + 1;
                        $display("[FAIL] %0s: phase %0d lasted %0d cycles, expected %0d (t=%0t)",
                                 (jj == 0) ? "A" : "B", ps[jj], rl[jj], exp_len(jj, ps[jj]), $time);
                    end
                    if (st != next_s(ps[jj])) begin
                        errors = errors + 1;
                        $display("[FAIL] %0s: phase order %0d -> %0d (t=%0t)",
                                 (jj == 0) ? "A" : "B", ps[jj], st, $time);
                    end
                end
                ps[jj] = st;
                rl[jj] = 1;
            end
        end
    end

    // ------------------------------------------------------------------
    // Stimulus
    // ------------------------------------------------------------------
    integer k, s;
    integer b_wa, b_wb, b_na, b_nb;
    integer base_log, seq_ok, alt_ok;

    initial begin : stimulus
        expns[0] = 0; expns[1] = 0; rawst[0] = 0; rawst[1] = 0;
        rl[0] = 0; rl[1] = 0; ps[0] = 0; ps[1] = 0;

        // ---- S1: reset and normal operation ----
        rst_n = 1'b0;
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        check(1'b1, "S1 reset released");
        wait_cycles(200);

        // ---- S2: density sweep (A: 0..7, B: 7..0) ----
        for (k = 0; k < 8; k = k + 1) begin
            da = k; db = 7 - k;
            wait_cycles(100);
        end
        // densities change every cycle: NS length must still follow density at entry
        for (k = 0; k < 300; k = k + 1) begin
            da = $random; db = $random;
            @(negedge clk);
        end
        // both directions at maximum density: each keeps >= MIN green, nobody starves
        da = 3'd7; db = 3'd7;
        wait_cycles(150);
        da = 3'd0; db = 3'd0;
        wait_cycles(100);
        da = 3'd3; db = 3'd3;
        wait_cycles(100);

        // ---- S3: pedestrian cases ----
        b_wa = n_walk_a; b_wb = n_walk_b;
        @(negedge clk) pra = 1'b1;
        @(negedge clk) pra = 1'b0;
        wait_cycles(120);
        check(n_walk_a - b_wa == 1 && n_walk_b - b_wb == 0, "S3a single request A -> one walk, none for B");

        b_wa = n_walk_a; b_wb = n_walk_b;
        @(negedge clk) begin pra = 1'b1; prb = 1'b1; end
        @(negedge clk) begin pra = 1'b0; prb = 1'b0; end
        wait_cycles(150);
        check(n_walk_a - b_wa == 1 && n_walk_b - b_wb == 1, "S3b simultaneous requests A and B -> one walk each");

        b_wa = n_walk_a;
        wait (uut.u_junction_a.state == 4'd2);       // request during NS yellow
        @(negedge clk) pra = 1'b1;
        @(negedge clk) pra = 1'b0;
        wait_cycles(120);
        check(n_walk_a - b_wa == 1, "S3c request during yellow is neither lost nor doubled");

        b_wa = n_walk_a;
        @(negedge clk) pra = 1'b1;
        wait_cycles(25);                              // held level
        @(negedge clk) pra = 1'b0;
        wait_cycles(120);
        check(n_walk_a - b_wa == 1, "S3d held request level for 25 cycles -> one walk");

        b_na = n_new_a; b_wa = n_walk_a;
        @(negedge clk) begin emg = 1'b1; pra = 1'b1; end
        wait_cycles(3);
        @(negedge clk) begin emg = 1'b0; pra = 1'b0; end
        wait_cycles(150);
        check(n_walk_a - b_wa == 1, "S3e request during emergency is kept and served after release");

        // ---- S4: contested pedestrian slots: 40 simultaneous pairs, 110 cycles apart ----
        // A pair needs two slots (one walk per slot), so the pairs are spaced two signal cycles apart.
        wait_cycles(100);
        b_wa = n_walk_a; b_wb = n_walk_b; base_log = n_walks_total;
        for (k = 0; k < 40; k = k + 1) begin
            @(negedge clk) begin pra = 1'b1; prb = 1'b1; end
            @(negedge clk) begin pra = 1'b0; prb = 1'b0; end
            wait_cycles(110);
        end
        check(n_walk_a - b_wa == 40 && n_walk_b - b_wb == 40,
              "S4 contested pairs: 40 walks for A and 40 for B (no starvation)");
        seq_ok = 1; alt_ok = 1;
        for (k = 0; k < 40; k = k + 1) begin
            if (walk_log[base_log + 2*k] == walk_log[base_log + 2*k + 1]) seq_ok = 0;
            if (k > 0 && walk_log[base_log + 2*k] == walk_log[base_log + 2*k - 2]) alt_ok = 0;
        end
        check(seq_ok, "S4 in every contested pair the two walks go to different junctions");
        check(alt_ok, "S4 the junction served first alternates between consecutive contested pairs");

        // ---- S5: emergency asserted in every phase of A, then of B ----
        for (s = 1; s <= 7; s = s + 1) begin
            wait (uut.u_junction_a.state == s);
            @(negedge clk) emg = 1'b1;
            @(posedge clk) #1;
            check(nsA == 2'b00 && ewA == 2'b00 && nsB == 2'b00 && ewB == 2'b00,
                  "S5 emergency in A-phase: both junctions all-red after 1 cycle");
            wait_cycles(3);
            @(negedge clk) emg = 1'b0;
            wait_cycles(70);
        end
        for (s = 1; s <= 7; s = s + 1) begin
            wait (uut.u_junction_b.state == s);
            @(negedge clk) emg = 1'b1;
            @(posedge clk) #1;
            check(nsA == 2'b00 && ewA == 2'b00 && nsB == 2'b00 && ewB == 2'b00,
                  "S5 emergency in B-phase: both junctions all-red after 1 cycle");
            wait_cycles(3);
            @(negedge clk) emg = 1'b0;
            wait_cycles(70);
        end
        // override while Junction B is waiting for the green-wave pulse (GW_WAIT)
        @(negedge clk) emg = 1'b1;
        wait_cycles(2);
        @(negedge clk) emg = 1'b0;
        wait (uut.u_junction_b.state == 4'd0);
        @(negedge clk) emg = 1'b1;
        @(posedge clk) #1;
        check(nsA == 2'b00 && ewA == 2'b00 && nsB == 2'b00 && ewB == 2'b00,
              "S5 emergency while B waits in GW_WAIT: all-red and wait state preserved");
        wait_cycles(3);
        @(negedge clk) emg = 1'b0;
        wait_cycles(70);

        // override during an ACTIVE pedestrian walk (not just the PED state): Junction A, then Junction B
        wait (uut.u_junction_a.state == 4'd4);
        b_wa = n_walk_a;
        @(negedge clk) pra = 1'b1;
        @(negedge clk) pra = 1'b0;
        wait (wA == 1'b1);
        wait_cycles(2);
        @(negedge clk) emg = 1'b1;
        @(posedge clk) #1;
        check(wA == 1'b0 && wB == 1'b0 && nsA == 2'b00 && ewA == 2'b00 && nsB == 2'b00 && ewB == 2'b00,
              "S5 override during an ACTIVE walk (A): walk and all lights off after 1 cycle");
        wait_cycles(3);
        @(negedge clk) emg = 1'b0;
        wait_cycles(150);
        check(n_walk_a - b_wa == 1, "S5 the walk cut by the override is counted once and not repeated (A)");

        wait (uut.u_junction_b.state == 4'd4);
        b_wb = n_walk_b;
        @(negedge clk) prb = 1'b1;
        @(negedge clk) prb = 1'b0;
        wait (wB == 1'b1);
        wait_cycles(2);
        @(negedge clk) emg = 1'b1;
        @(posedge clk) #1;
        check(wA == 1'b0 && wB == 1'b0 && nsA == 2'b00 && ewA == 2'b00 && nsB == 2'b00 && ewB == 2'b00,
              "S5 override during an ACTIVE walk (B): walk and all lights off after 1 cycle");
        wait_cycles(3);
        @(negedge clk) emg = 1'b0;
        wait_cycles(150);
        check(n_walk_b - b_wb == 1, "S5 the walk cut by the override is counted once and not repeated (B)");

        // rapid toggle: override every other cycle with no gap
        for (k = 0; k < 40; k = k + 1) begin
            @(negedge clk) emg = 1'b1;
            @(negedge clk) emg = 1'b0;
        end
        wait_cycles(70);

        // ---- S6: reset asserted during an active count ----
        wait_cycles(17);
        rst_n = 1'b0;
        #1 check(nsA == 2'b00 && ewA == 2'b00 && nsB == 2'b00 && ewB == 2'b00,
                 "S6 outputs are all-red immediately when reset is asserted mid-count");
        wait_cycles(2);
        rst_n = 1'b1;
        @(posedge clk) #1;
        check(uut.rst_n_sync == 1'b0, "S6 reset release is synchronised: still held one clock after rst_n rises");
        @(posedge clk) #1;
        check(uut.rst_n_sync == 1'b1, "S6 reset release completes two clocks after rst_n rises");
        wait_cycles(150);
        check(1'b1, "S6 mid-count reset: system restarts and offset is re-established");

        // ---- S7: constrained-random run (20 000 cycles) ----
        b_na = n_new_a; b_nb = n_new_b; b_wa = n_walk_a; b_wb = n_walk_b;
        for (k = 0; k < 20000; k = k + 1) begin
            @(negedge clk);
            emg = ({$random} % 100) == 0;          // ~1% overrides
            pra = ({$random} % 100) < 8;           // ~8% pedestrian requests
            prb = ({$random} % 100) < 8;
            da  = {$random};
            db  = {$random};
        end
        @(negedge clk) begin emg = 1'b0; pra = 1'b0; prb = 1'b0; da = 3'd3; db = 3'd3; end
        wait_cycles(400);
        check(n_walk_a - b_wa == n_new_a - b_na,
              "S7 random: every request finding nothing pending got exactly one walk (A)");
        check(n_walk_b - b_wb == n_new_b - b_nb,
              "S7 random: every request finding nothing pending got exactly one walk (B)");

        // ---- S8: integrated arbitration fairness, 120 contested pairs (more than 100 per junction) ----
        wait_cycles(150);
        b_wa = n_walk_a; b_wb = n_walk_b; base_log = n_walks_total;
        for (k = 0; k < 120; k = k + 1) begin
            @(negedge clk) begin pra = 1'b1; prb = 1'b1; end
            @(negedge clk) begin pra = 1'b0; prb = 1'b0; end
            wait_cycles(110);
        end
        check(n_walk_a - b_wa == 120 && n_walk_b - b_wb == 120,
              "S8 integrated fairness: 120 contested pairs -> 120 walks for A and 120 for B");
        seq_ok = 1; alt_ok = 1;
        for (k = 0; k < 120; k = k + 1) begin
            if (walk_log[base_log + 2*k] == walk_log[base_log + 2*k + 1]) seq_ok = 0;
            if (k > 0 && walk_log[base_log + 2*k] == walk_log[base_log + 2*k - 2]) alt_ok = 0;
        end
        check(seq_ok, "S8 every contested pair is split between the two junctions");
        check(alt_ok, "S8 the first-served junction alternates on every one of the 120 contests (no fixed priority)");

        // ---- final report ----
        $display("--------------------------------------------------------------");
        $display("Cycles monitored with invariants : %0d", inv_cycles);
        $display("Green-wave entries verified      : %0d", offset_checks);
        $display("Pedestrian walks served (A / B)  : %0d / %0d", n_walk_a, n_walk_b);
        $display("Discrete checks                  : %0d", checks);
        $display("Errors                           : %0d", errors);
        if (errors == 0) $display("RESULT: PASS");
        else             $display("RESULT: FAIL");
        $display("--------------------------------------------------------------");
        $finish;
    end

endmodule
