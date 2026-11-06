`timescale 1ns / 1ps
// Scenario testbench that prints one CSV line per clock cycle (prefix "W,") for waveform plotting.
// The same stimulus can be loaded in ModelSim: add wave -r /wave_tb/* ; run -all
module wave_tb;
    reg        clk = 1'b0;
    reg        rst_n = 1'b0;
    reg        emg = 1'b0;
    reg  [2:0] da = 3'd3;
    reg  [2:0] db = 3'd3;
    reg        pra = 1'b0;
    reg        prb = 1'b0;
    wire [1:0] nsA, ewA, nsB, ewB;
    wire       wA, wB;
    integer    c = 0;
    integer    k;

    amtgc_top uut (
        .clk(clk), .rst_n(rst_n), .emergency_override(emg),
        .density_a(da), .density_b(db), .ped_req_a(pra), .ped_req_b(prb),
        .ns_lights_a(nsA), .ew_lights_a(ewA), .ped_walk_a(wA),
        .ns_lights_b(nsB), .ew_lights_b(ewB), .ped_walk_b(wB)
    );

    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (uut.rst_n_sync) begin
            $display("W,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                     c, emg, nsA, ewA, wA, nsB, ewB, wB, uut.ped_slot,
                     uut.u_junction_a.ped_req_out, uut.u_junction_b.ped_req_out,
                     uut.ped_grant_a, uut.ped_grant_b, pra, prb, da, db,
                     uut.u_junction_a.state, uut.u_junction_b.state, uut.gw_sync_a);
            c = c + 1;
        end
    end

    task idle; input integer n; begin repeat (n) @(negedge clk); end endtask

    initial begin
        rst_n = 1'b0; repeat (3) @(negedge clk); rst_n = 1'b1;
        // 1) normal operation, density 3 / 3, with one pedestrian press on each junction
        idle(20);
        @(negedge clk) begin pra = 1'b1; end @(negedge clk) pra = 1'b0;
        idle(120);
        // 2) adaptive timing: density 0..7 on both junctions, one value per signal cycle
        for (k = 0; k < 8; k = k + 1) begin da = k; db = k; idle(47); end
        da = 3'd7; db = 3'd7; idle(200);
        da = 3'd3; db = 3'd3; idle(60);
        // 3) pedestrian arbitration: 4 contested pairs, 110 cycles apart
        for (k = 0; k < 4; k = k + 1) begin
            @(negedge clk) begin pra = 1'b1; prb = 1'b1; end
            @(negedge clk) begin pra = 1'b0; prb = 1'b0; end
            idle(110);
        end
        // 4) emergency: during A's pedestrian slot, then during A's NS green, then toggled with no gap
        wait (uut.u_junction_a.state == 4'd4);          // A in EW green: the next slot is ahead
        @(negedge clk) begin pra = 1'b1; end @(negedge clk) pra = 1'b0;
        wait (wA == 1'b1);                              // the pedestrian walk is now active
        idle(2);
        @(negedge clk) emg = 1'b1; idle(6); @(negedge clk) emg = 1'b0;
        idle(120);
        wait (uut.u_junction_a.state == 4'd1);
        idle(5);
        @(negedge clk) emg = 1'b1; idle(5); @(negedge clk) emg = 1'b0;
        idle(5);
        for (k = 0; k < 3; k = k + 1) begin @(negedge clk) emg = 1'b1; @(negedge clk) emg = 1'b0; end
        idle(150);
        $finish;
    end
endmodule
