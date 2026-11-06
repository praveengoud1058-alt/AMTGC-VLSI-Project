`timescale 1ns/1ps
module xcheck_tb;
  reg clk = 0; reg rst_n = 0; reg emg = 0; reg [2:0] da = 3, db = 5; reg pra = 0, prb = 0;
  wire [1:0] nsA, ewA, nsB, ewB; wire wA, wB;
  integer c = 0;
  amtgc_top uut (.clk(clk), .rst_n(rst_n), .emergency_override(emg), .density_a(da), .density_b(db),
     .ped_req_a(pra), .ped_req_b(prb), .ns_lights_a(nsA), .ew_lights_a(ewA), .ped_walk_a(wA),
     .ns_lights_b(nsB), .ew_lights_b(ewB), .ped_walk_b(wB));
  always #5 clk = ~clk;
  // inputs for cycle c, applied at the falling edge before posedge c
  always @(negedge clk) begin
    da  = (c < 50) ? 3 : 7;
    db  = 5;
    pra = (c == 10) || (c == 60);
    prb = (c == 12) || (c == 60);
    emg = (c >= 80) && (c <= 82);
  end
  always @(posedge clk) begin
    if (uut.rst_n_sync && c < 200) begin
      $display("%0d %0d %0d %0d %0d %0d %0d", c, nsA, ewA, wA, nsB, ewB, wB);
      c = c + 1;
    end
  end
  initial begin
    rst_n = 0; repeat (3) @(negedge clk); rst_n = 1;
    repeat (260) @(negedge clk);
    $finish;
  end
endmodule
