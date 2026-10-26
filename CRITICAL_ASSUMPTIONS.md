# CRITICAL ASSUMPTIONS & POTENTIAL ERRORS - DETAILED ANALYSIS

================================================================================
CRITICAL ASSUMPTION #1: PHASE THRESHOLDS (65% and 80%)
================================================================================

### Current Implementation (UPDATED Jan 12, 2026 - Binary Classification):
```python
clear = len(data[data['transmission_pct'] >= 70])      # ≥70% = Clear (no precipitate)
precipitate = len(data[data['transmission_pct'] < 70])  # <70% = Precipitate (deposition)
```

### Threshold Rationale:
- **70% (Clear/Precipitate boundary):** Based on observed transmission distribution tail extending to ~70%
- **Simplified binary model:** Focuses on key distinction for deposition applications (clear vs precipitate)

### Questions This Raises:
1. WHERE DID THESE VALUES COME FROM?
   - Are they industry standard?
   - Are they defined in your lab procedures?
   - Should they be different?

2. BOUNDARY CONDITIONS:
   - transmission_pct = 65.0 exactly → classified as TURBID
   - transmission_pct = 80.0 exactly → classified as TURBID
   - transmission_pct = 80.001 → classified as CLEAR
   - Is this correct?

3. SEMANTIC QUESTION:
   - Does "clear" really mean > 80%?
   - Does "phase-separated" really mean < 65%?
   - What is transmission % measuring exactly?

### IMPACT IF WRONG:
If these thresholds are off by just 5%, results could change dramatically:

Example - DADMAC/SCG analysis:
- Current: 100.0% phase-separated (0% clear, 0% turbid)
- If threshold 70%/85%: Could be 0% phase-sep, 100% turbid or clear
- This REVERSES the conclusion (excellent → poor)

### VERIFICATION NEEDED:
Run this check on your actual data:
```
SELECT 
  CAST(transmission_pct AS INTEGER) as trans_bucket,
  COUNT(*) as count
FROM measurements
WHERE polymer_name = 'DADMAC' AND surfactant_name = 'SCG'
  AND timepoint_minutes = (SELECT MAX(timepoint_minutes) FROM measurements)
GROUP BY CAST(transmission_pct AS INTEGER)
ORDER BY trans_bucket DESC
```

This will show you the actual transmission distribution and let you verify
the thresholds make sense.

================================================================================
CRITICAL ASSUMPTION #2: 95% EQUILIBRATION CRITERION
================================================================================

### Current Implementation:
```python
final_avg = timepoint_stats.iloc[-1]
threshold_95 = final_avg * 0.95
eq_mask = timepoint_stats >= threshold_95
eq_time = timepoint_stats[eq_mask].index[0]
```

### What This Means:
- Takes LAST measured timepoint as "final"
- Defines equilibrium as first timepoint >= 95% of that final value
- NOT comparing to theoretical equilibrium (e.g., 100% transmission)

### ASSUMPTION: Final timepoint = true equilibrium
- What if kinetics haven't fully stopped at final timepoint?
- What if system is drifting downward (kinetically active)?
- Example: if final_avg = 23%, we call 21.85% "equilibrium"

### Questions:
1. Should we use 95% criterion or compare to actual expected value?
2. For DADMAC/SCG with final=23%, is that actually equilibrium?
   - Or is it still changing at 60+ minutes?
3. For clear systems (>80%), does 95% criterion make sense?

### IMPACT:
If system isn't stable at final timepoint, equilibration times could be WRONG

### How to Verify:
Look at last 3-4 timepoints. Are they flat or still drifting?
```
SELECT 
  timepoint_minutes,
  AVG(transmission_pct) as avg_trans,
  STDDEV(transmission_pct) as std_trans,
  COUNT(*) as n_wells
FROM measurements
WHERE experiment_id = 'exp_20260102_scg_dadmac'  -- or similar
GROUP BY timepoint_minutes
ORDER BY timepoint_minutes DESC
LIMIT 10
```

If final values are steady → 95% criterion makes sense
If final values are drifting → might need adjustment

================================================================================
CRITICAL ASSUMPTION #3: EQUILIBRIUM TIMEPOINT IN PRESENTATION
================================================================================

### Issue Identified:
```python
# Current code returns NEXT timepoint after threshold reached
if row['avg_trans'] >= threshold_95:
    next_idx = df[df['timepoint_minutes'] >= row['timepoint_minutes']].index[0]
    if next_idx < len(df) - 1:
        return df['timepoint_minutes'].iloc[next_idx + 1]  # THIS LINE
```

### Example:
- Equilibration reached at 54.02 min → function returns 61.53 min (NEXT timepoint)
- This adds ~7.5 minutes to reported time
- Is this intentional?

### Two Interpretations:
1. "First timepoint where equilibrium IS reached" = 54.02 min (analysis_polymers.py)
2. "First timepoint AFTER equilibrium reached" = 61.53 min (generate_presentation.py)

### Which is correct?
- For kinetics analysis: Use 54.02 (when equilibrium actually reached)
- For presentation data: Use 61.53 (next measurement point to ensure equilibrium)

### VERIFY: Check if this inconsistency matters
- Does it affect your conclusions?
- Should analysis and presentation use same timepoint?

================================================================================
CRITICAL ASSUMPTION #4: RBF INTERPOLATION
================================================================================

### Current Settings:
```python
rbf = Rbf(surf_conc, poly_conc, transmission, function='thin_plate')
```

### What This Does:
1. Takes 192 data points (2 plates × 96 wells each)
2. Fits thin plate spline through them
3. Interpolates to 50×50 grid for visualization

### ISSUES WITH THIS APPROACH:

1. MODERATE SPARSITY:
   - 192 points in 2D space (log-log scale)
   - That's ~19.2 points per log decade (better than I initially said)
   - 50×50 = 2500 interpolated points
   - Still interpolating from sparse data, but less sparse than expected

2. POTENTIAL ARTIFACTS:
   - RBF can oscillate between data points
   - Log scale might create weird artifacts
   - No validation that interpolated values make sense

3. BOUNDARY EFFECTS:
   - What happens outside the data range?
   - Do contours extrapolate beyond measured points?

### How to Verify:
1. Plot the original 192 data points on top of RBF surface
2. Check that contours pass through/near your actual measurements
3. Look for unrealistic smooth regions between data points

### Red Flags to Watch For:
- Contours that smoothly connect distant points
- Transmission values outside 0-100% range
- Unrealistic surface artifacts

================================================================================
GUESSES AND UNKNOWNS IN THE CODE
================================================================================

I AM GUESSING AT (NO DOCUMENTATION):
1. ❌ 65% and 80% transmission thresholds - origin unknown
2. ❌ 95% equilibration criterion - why this value?
3. ❌ Thin plate RBF - why this interpolator?
4. ❌ 50×50 grid resolution - why this size?
5. ❌ Surfactant/polymer concentration formulas - origin?
6. ❌ UTF-16 encoding for transmission files - confirmed?
7. ❌ Well ordering (column-wise not row-wise) - still correct?

I AM CONFIDENT ABOUT (VERIFIED):
1. ✓ Kinetic time-series aggregation method
2. ✓ Equilibration calculation logic (method is sound)
3. ✓ SQL query structure and data retrieval
4. ✓ Phase classification logic (boundaries handled correctly)
5. ✓ Matplotlib plotting and figure generation
6. ✓ No null/NaN values in key columns
7. ✓ All 96 wells present at each timepoint

================================================================================
RECOMMENDATIONS FOR VERIFICATION
================================================================================

PRIORITY 1 (DO FIRST):
☐ Confirm transmission thresholds: 65% and 80%
  → This affects ALL conclusions
  
☐ Confirm 95% equilibration criterion is appropriate
  → This affects kinetic conclusions

☐ Check last 3 timepoints for each experiment
  → Are they stable or still drifting?

PRIORITY 2 (IMPORTANT):
☐ Verify concentration calculation formulas
  → Are the surfactant_pct and polymer_pct correct?

☐ Plot RBF surface with original 96 data points overlay
  → Check for artifacts or unrealistic interpolation

☐ Clarify equilibrium timepoint intention
  → Should presentation use 54.02 or 61.53?

PRIORITY 3 (NICE TO HAVE):
☐ Expand Excel/JR30M testing
  → Current data insufficient (1 surfactant only)

☐ Validate 50×50 grid resolution
  → Is it sufficient? Too much?

☐ Document WHY threshold values were chosen
  → For future reference and reproducibility

================================================================================

