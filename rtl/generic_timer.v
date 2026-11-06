`timescale 1ns / 1ps

module generic_timer #(
    parameter COUNTER_WIDTH = 8
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     start,
    input  wire [COUNTER_WIDTH-1:0] count_target,
    output reg                      done,
    output reg  [COUNTER_WIDTH-1:0] current_count
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_count <= {COUNTER_WIDTH{1'b0}};
            done          <= 1'b0;
        end else if (!start) begin
            current_count <= {COUNTER_WIDTH{1'b0}};
            done          <= 1'b0;
        end else begin
            if (count_target == {COUNTER_WIDTH{1'b0}}) begin
                done          <= 1'b1;
                current_count <= {COUNTER_WIDTH{1'b0}};
            end else if (current_count >= count_target - 1'b1) begin
                done          <= 1'b1;
                current_count <= current_count;
            end else begin
                current_count <= current_count + 1'b1;
                done          <= 1'b0;
            end
        end
    end

endmodule
