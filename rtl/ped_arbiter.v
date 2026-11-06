`timescale 1ns / 1ps
// ============================================================================
// ped_arbiter
//   Shared pedestrian arbiter for both junctions. Interacts ONLY through the
//   request/grant handshake; it has no access to junction internal state.
//
//   amtgc_top gives both junctions the same pedestrian-slot strobe, so a junction
//   with a pending pedestrian raises its request in the same clock cycle as the
//   other one. Grants are combinational and at most one is high: ONE walk is
//   served per slot. The junction that is not granted keeps its request pending
//   and presents it again at the next slot.
//
//   Fairness: round-robin pointer 'prefer_b'. It moves ONLY when both requests are
//   present in the same cycle (a contest). The contest loser gets priority at the
//   next contest, so a contested requester waits at most one slot behind the other
//   junction. A lone request is always granted and never moves the pointer, so
//   uncontested traffic cannot skew later contests.
//   Reset: prefer_b = 0 (Junction A wins the first contest).
// ============================================================================
module ped_arbiter (
    input  wire clk,
    input  wire rst_n,
    input  wire req_a,
    input  wire req_b,
    output wire grant_a,
    output wire grant_b
);
    reg prefer_b;

    assign grant_a = req_a & (~req_b | ~prefer_b);
    assign grant_b = req_b & ~grant_a;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            prefer_b <= 1'b0;
        else if (req_a & req_b)
            prefer_b <= ~prefer_b;
    end

endmodule
