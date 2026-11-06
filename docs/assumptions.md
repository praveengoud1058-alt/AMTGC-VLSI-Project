# Design assumptions (final)

1. Clock: single synchronous clock domain. The timing numbers in the report assume
   100 MHz (10 ns period), but nothing in the RTL depends on the frequency.
2. Reset: active-low, asynchronous assertion, synchronous de-assertion through a
   2-flop synchroniser in `amtgc_top`. This matches the implementation. Earlier
   documents claimed synchronous de-assertion without implementing it; see bug_log BUG-07.
3. Green-wave offset: `GW_DELAY_CYCLES = 4` cycles, measured from Junction A's NS-green
   entry to Junction B's NS-green entry. Minimum value supported: 2.
4. Density: 3-bit linear encoding; 0 = minimal traffic, 7 = saturated. Density is
   sampled once per signal cycle, at NS-green entry.
5. Phase lengths are exact cycle counts. Minimum phase length is 3 cycles.
6. Safety gap: each direction has an all-red interval of `RED_TIME` = 3 cycles
   before the opposing green. A red interval also follows the EMERGENCY state.
7. Pedestrian slot: a fixed `PED_TIME` = 5 cycles in every signal cycle. The walk
   signal is asserted only if a request was granted. One walk is granted per arbitration slot, and
   Junction A's decision strobe defines the slot for both junctions (see architecture_final.md section 7).
8. Pedestrian requests pending at reset are discarded. A request pending during an emergency override is kept.
9. Emergency override is a level signal that may be held for any length of time,
   including zero gap between assertions.
10. Only the two junctions described are modelled. Turning movements, sensors and
    vehicle detection are out of scope.
