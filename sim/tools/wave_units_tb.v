`timescale 1ns / 1ps
// Per-cycle CSV trace of the two Task-2 modules on their own (prefix "T," = generic_timer, "J," = junction_controller).
// Each part has its own reset and idle task, so the two stimulus threads never share state.
// Runs under iverilog and under the bundled sim/tools/vsim.py.
module wave_units_tb;
    reg        clk = 1'b0;
    always #5 clk = ~clk;

    // ------------------------------ generic_timer ------------------------------
    reg        rst_t = 1'b0;
    reg        start = 1'b0;
    reg  [7:0] target = 8'd0;
    wire       tdone;
    wire [7:0] tcount;
    integer    ct = 0;
    reg        t_fin = 1'b0;

    generic_timer #(.COUNTER_WIDTH(8)) u_timer (
        .clk(clk), .rst_n(rst_t), .start(start), .count_target(target),
        .done(tdone), .current_count(tcount)
    );

    always @(posedge clk) begin
        $display("T,%0d,%0d,%0d,%0d,%0d,%0d", ct, rst_t, start, target, tcount, tdone);
        ct = ct + 1;
    end

    task idle_t; input integer n; begin repeat (n) @(negedge clk); end endtask

    initial begin
        rst_t = 1'b0; idle_t(2); rst_t = 1'b1; idle_t(2);
        target = 8'd5; start = 1'b1; idle_t(8); start = 1'b0; idle_t(3);      // run 1: target 5
        target = 8'd0; start = 1'b1; idle_t(4); start = 1'b0; idle_t(3);      // run 2: target 0
        target = 8'd1; start = 1'b1; idle_t(4); start = 1'b0; idle_t(3);      // run 3: target 1
        target = 8'd8; start = 1'b1; idle_t(4);                               // run 4: reset while counting
        rst_t = 1'b0; idle_t(2); rst_t = 1'b1; idle_t(12); start = 1'b0; idle_t(3);
        target = 8'd3; start = 1'b1; idle_t(6); start = 1'b0; idle_t(3);      // run 5: target 3 after the reset
        t_fin = 1'b1;
    end

    // ------------------------------ junction_controller (Junction-A parameters, density 3) ------------------------------
    reg        rst_j = 1'b0;
    reg        preq = 1'b0;
    wire [1:0] jns, jew;
    wire       jwalk, jreq, jslot, jsync;
    integer    cj = 0;
    reg        j_fin = 1'b0;

    junction_controller #(
        .COUNTER_WIDTH(8), .BASE_GREEN(6), .MIN_GREEN(6), .MAX_GREEN(24), .DENSITY_STEP(3),
        .YELLOW_TIME(3), .RED_TIME(3), .PED_TIME(5), .IS_JUNCTION_B(1'b0)
    ) u_dut (
        .clk(clk), .rst_n(rst_j), .emergency_override(1'b0), .traffic_density(3'd3),
        .ped_req_in(preq), .ped_grant(jreq), .ped_req_out(jreq), .ped_slot_in(jslot), .ped_slot_out(jslot),
        .gw_sync_in(1'b0), .gw_sync_out(jsync),
        .ns_lights(jns), .ew_lights(jew), .ped_walk(jwalk)
    );

    always @(posedge clk) begin
        $display("J,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d", cj, rst_j, u_dut.state, jns, jew, jwalk,
                 preq, u_dut.ped_pending, u_dut.ped_serve);
        cj = cj + 1;
    end

    task idle_j; input integer n; begin repeat (n) @(negedge clk); end endtask

    initial begin
        rst_j = 1'b0; idle_j(2); rst_j = 1'b1; idle_j(10);
        wait (u_dut.state == 4'd2);                                           // NS yellow
        @(negedge clk) preq = 1'b1;                                           // request arrives during yellow
        @(negedge clk) preq = 1'b0;
        idle_j(100);
        @(negedge clk) preq = 1'b1; idle_j(20); preq = 1'b0;                  // request held high for 20 cycles
        idle_j(100);
        j_fin = 1'b1;
    end

    initial begin
        wait (t_fin && j_fin);
        idle_t(2);
        $finish;
    end

    initial begin
        #400000;
        $display("[FAIL] watchdog: wave_units_tb did not finish");
        $display("RESULT: FAIL");
        $finish;
    end
endmodule
