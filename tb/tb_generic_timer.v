`timescale 1ns / 1ps
// ============================================================================
// Self-checking testbench for generic_timer (unmodified RTL).
// The same testbench is run with three COUNTER_WIDTH values without editing it:
//   iverilog -P tb_generic_timer.COUNTER_WIDTH=4  ...
//   iverilog -P tb_generic_timer.COUNTER_WIDTH=8  ...   (default)
//   iverilog -P tb_generic_timer.COUNTER_WIDTH=12 ...
// Expected behaviour (derived from the RTL):
//   * done rises exactly max(target,1) clock edges after start is raised.
//   * current_count equals max(target-1,0) when done is high.
//   * start low clears done and current_count on the next edge.
//   * an asynchronous reset while counting clears both immediately.
// ============================================================================
module tb_generic_timer;
    parameter COUNTER_WIDTH = 8;

    reg                      clk = 1'b0;
    reg                      rst_n = 1'b0;
    reg                      start = 1'b0;
    reg  [COUNTER_WIDTH-1:0] count_target = {COUNTER_WIDTH{1'b0}};
    wire                     done;
    wire [COUNTER_WIDTH-1:0] current_count;

    generic_timer #(.COUNTER_WIDTH(COUNTER_WIDTH)) dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .start        (start),
        .count_target (count_target),
        .done         (done),
        .current_count(current_count)
    );

    always #5 clk = ~clk;

    // Watchdog: a self-checking testbench must never hang. A normal run ends far earlier than
    // 2000000 ns, so reaching it means a wait() never completed; that is reported as a FAIL.
    initial begin
        #2000000;
        $display("[FAIL] watchdog: testbench did not finish within 2000000 ns");
        $display("RESULT: FAIL");
        $finish;
    end

    integer errors = 0;
    integer checks = 0;
    integer edges;
    integer t;
    reg [COUNTER_WIDTH-1:0] maxt;

    task check;
        input        cond;
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

    // raise start with a target, count edges until done, then check
    task run_target;
        input [COUNTER_WIDTH-1:0] tgt;
        integer exp_edges;
        integer exp_cnt;
        begin
            @(negedge clk);
            count_target = tgt;
            start = 1'b1;
            edges = 0;
            while (!done && edges < 10000) begin
                @(posedge clk); #1;
                edges = edges + 1;
            end
            exp_edges = (tgt == 0) ? 1 : tgt;
            exp_cnt   = (tgt == 0) ? 0 : tgt - 1;
            if (edges != exp_edges)
                $display("       target=%0d: done after %0d edges, expected %0d", tgt, edges, exp_edges);
            check(edges == exp_edges, "done asserts after exactly max(target,1) clock edges");
            check(current_count == exp_cnt, "current_count equals target-1 (0 for target 0) when done");
            // done must stay high while start is held
            @(posedge clk); #1;
            check(done == 1'b1, "done holds while start stays high");
            // release start: done and count clear on next edge
            @(negedge clk);
            start = 1'b0;
            @(posedge clk); #1;
            check(done == 1'b0 && current_count == 0, "start low clears done and current_count");
            @(negedge clk);
        end
    endtask

    initial begin
        maxt = {COUNTER_WIDTH{1'b1}};
        rst_n = 1'b0;
        repeat (3) @(posedge clk);
        @(negedge clk) rst_n = 1'b1;
        @(negedge clk);

        run_target(0);
        run_target(1);
        run_target(2);
        run_target(maxt / 2);
        run_target(maxt);

        // asynchronous reset while counting
        @(negedge clk);
        count_target = maxt; start = 1'b1;
        repeat (4) @(posedge clk);
        #1;
        check(current_count != 0, "counter is running before reset");
        @(negedge clk) rst_n = 1'b0;   // assert mid-count (asynchronous)
        #1;
        check(current_count == 0 && done == 1'b0, "asynchronous reset clears count and done mid-count");
        @(negedge clk) rst_n = 1'b1;
        start = 1'b0;
        @(negedge clk);

        $display("----------------------------------------------");
        $display("generic_timer COUNTER_WIDTH=%0d : %0d checks, %0d errors", COUNTER_WIDTH, checks, errors);
        if (errors == 0) $display("RESULT: PASS");
        else             $display("RESULT: FAIL");
        $display("----------------------------------------------");
        $finish;
    end

endmodule
