@echo off
rem Windows: run from the repository root with Icarus Verilog on PATH.
if not exist sim\logs mkdir sim\logs
if not exist sim\build mkdir sim\build
iverilog -g2005 -Ptb_generic_timer.COUNTER_WIDTH=4  -o sim\build\timer_w4.vvp  rtl\generic_timer.v tb\tb_generic_timer.v && vvp -n sim\build\timer_w4.vvp  > sim\logs\tb_generic_timer_w4.log
iverilog -g2005 -Ptb_generic_timer.COUNTER_WIDTH=8  -o sim\build\timer_w8.vvp  rtl\generic_timer.v tb\tb_generic_timer.v && vvp -n sim\build\timer_w8.vvp  > sim\logs\tb_generic_timer_w8.log
iverilog -g2005 -Ptb_generic_timer.COUNTER_WIDTH=12 -o sim\build\timer_w12.vvp rtl\generic_timer.v tb\tb_generic_timer.v && vvp -n sim\build\timer_w12.vvp > sim\logs\tb_generic_timer_w12.log
iverilog -g2005 -o sim\build\jc.vvp rtl\generic_timer.v rtl\junction_controller.v tb\tb_junction_controller.v && vvp -n sim\build\jc.vvp > sim\logs\tb_junction_controller.log
iverilog -g2005 -o sim\build\arb.vvp rtl\ped_arbiter.v tb\tb_ped_arbiter.v && vvp -n sim\build\arb.vvp > sim\logs\tb_ped_arbiter.log
iverilog -g2005 -o sim\build\top.vvp rtl\generic_timer.v rtl\junction_controller.v rtl\ped_arbiter.v rtl\amtgc_top.v tb\tb_amtgc_top.v && vvp -n sim\build\top.vvp > sim\logs\tb_amtgc_top.log
echo Done. Check sim\logs\*.log for RESULT: PASS
