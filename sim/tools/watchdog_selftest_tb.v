`timescale 1ns / 1ps
// Self-test of the watchdog pattern used by every testbench in tb/.
// The wait() below can never complete, so the run must end through the watchdog with RESULT: FAIL.
// Expected: sim/logs/watchdog_selftest.log contains "[FAIL] watchdog" and "RESULT: FAIL".
module watchdog_selftest_tb;
    reg clk = 1'b0;
    reg never_set = 1'b0;
    always #5 clk = ~clk;
    initial begin
        wait (never_set == 1'b1);          // hang: never true
        $display("[PASS] unreachable");
        $finish;
    end
    initial begin
        #1000;
        $display("[FAIL] watchdog: testbench did not finish within 1000 ns");
        $display("RESULT: FAIL");
        $finish;
    end
endmodule
