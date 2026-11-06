`timescale 1ns / 1ps
// ============================================================================
// Self-checking testbench for ped_arbiter.
//   T1  lone requests are granted to the requester only; no request -> no grant
//   T2  simultaneous requests: exactly one grant per cycle, strict A/B alternation
//   T3  starvation check: A keeps its request asserted every cycle (worst case);
//       B must still receive a grant at least once every 2 cycles
//   T4  the round-robin pointer moves only on contested cycles (a lone grant never skews it)
// Grants are sampled 1 ns after each falling edge (combinational settle time).
// ============================================================================
module tb_ped_arbiter;
    reg  clk   = 1'b0;
    reg  rst_n = 1'b0;
    reg  req_a = 1'b0;
    reg  req_b = 1'b0;
    wire grant_a, grant_b;

    ped_arbiter dut (.clk(clk), .rst_n(rst_n), .req_a(req_a), .req_b(req_b),
                     .grant_a(grant_a), .grant_b(grant_b));

    always #5 clk = ~clk;

    // Watchdog: a self-checking testbench must never hang. A normal run ends far earlier than
    // 50000 ns, so reaching it means a wait() never completed; that is reported as a FAIL.
    initial begin
        #50000;
        $display("[FAIL] watchdog: testbench did not finish within 50000 ns");
        $display("RESULT: FAIL");
        $finish;
    end

    integer errors = 0;
    integer checks = 0;
    integer i, na, nb, gap_b, max_gap_b, last_g, alt_ok, onehot_ok;

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

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk) rst_n = 1'b1;

        // ---- T1: lone requesters ----
        @(negedge clk) begin req_a = 1'b1; req_b = 1'b0; end
        #1 check(grant_a == 1'b1 && grant_b == 1'b0, "T1a lone request A is granted");
        @(negedge clk) begin req_a = 1'b0; req_b = 1'b1; end
        #1 check(grant_a == 1'b0 && grant_b == 1'b1, "T1b lone request B is granted");
        @(negedge clk) begin req_a = 1'b0; req_b = 1'b0; end
        #1 check(grant_a == 1'b0 && grant_b == 1'b0, "T1c no request -> no grant");

        // ---- T2: simultaneous requests ----
        alt_ok = 1; onehot_ok = 1; last_g = 0; na = 0; nb = 0;
        for (i = 0; i < 40; i = i + 1) begin
            @(negedge clk) begin req_a = 1'b1; req_b = 1'b1; end
            #1;
            if (grant_a + grant_b != 1) onehot_ok = 0;
            if (grant_a) begin
                na = na + 1;
                if (last_g == 1) alt_ok = 0;
                last_g = 1;
            end
            if (grant_b) begin
                nb = nb + 1;
                if (last_g == 2) alt_ok = 0;
                last_g = 2;
            end
        end
        check(onehot_ok, "T2a simultaneous requests: exactly one grant every cycle");
        check(alt_ok,    "T2b simultaneous requests: strict A/B alternation (no fixed priority)");
        check(na == 20 && nb == 20, "T2c simultaneous requests: 20 grants to each over 40 cycles");

        // ---- T3: starvation under worst case (A always requesting) ----
        @(negedge clk) begin req_a = 1'b1; req_b = 1'b1; end
        gap_b = 0; max_gap_b = 0;
        for (i = 0; i < 100; i = i + 1) begin
            @(negedge clk); #1;
            if (grant_b) begin
                if (gap_b > max_gap_b) max_gap_b = gap_b;
                gap_b = 0;
            end else begin
                gap_b = gap_b + 1;
            end
        end
        check(max_gap_b <= 1, "T3 B is granted at least every 2 cycles while A always requests");

        // ---- T4: pointer memory (reset first so the pointer starts at 'A wins first contest') ----
        @(negedge clk) begin req_a = 1'b0; req_b = 1'b0; end
        @(negedge clk) rst_n = 1'b0;
        @(negedge clk) rst_n = 1'b1;
        @(negedge clk) begin req_a = 1'b1; req_b = 1'b1; end
        #1 check(grant_a == 1'b1 && grant_b == 1'b0, "T4a first contest after reset goes to A");
        @(negedge clk) begin req_a = 1'b0; req_b = 1'b1; end
        #1 check(grant_b == 1'b1, "T4b lone request B is granted between contests");
        @(negedge clk) begin req_a = 1'b1; req_b = 1'b1; end
        #1 check(grant_b == 1'b1 && grant_a == 1'b0, "T4c next contest goes to B (lone grant did not skew the pointer)");
        @(negedge clk) begin req_a = 1'b1; req_b = 1'b0; end
        #1 check(grant_a == 1'b1, "T4d lone request A is granted between contests");
        @(negedge clk) begin req_a = 1'b1; req_b = 1'b1; end
        #1 check(grant_a == 1'b1 && grant_b == 1'b0, "T4e next contest goes back to A");

        @(negedge clk) begin req_a = 1'b0; req_b = 1'b0; end
        $display("----------------------------------------------");
        $display("ped_arbiter : %0d checks, %0d errors", checks, errors);
        if (errors == 0) $display("RESULT: PASS");
        else             $display("RESULT: FAIL");
        $display("----------------------------------------------");
        $finish;
    end
endmodule
