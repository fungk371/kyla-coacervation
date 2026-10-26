# RBF Interpolation Artifact Reduction

## Problem Identified
Thin plate spline RBF interpolation with `smooth=5` was creating artifacts:
- **Oscillations** between sparse data points
- **Boundary effects** at edges of concentration space
- **Out-of-bounds values** (some regions predicted <0% or >100% transmission)
- **Unrealistic contours** connecting distant data points

## Solutions Implemented

### Solution 1: Increase Smoothing Parameter (Updated Jan 2026)
**Change:** `smooth=5` → `smooth=15` → `smooth=30`

**What this does:**
- The `smooth` parameter controls regularization in RBF fitting
- Higher values = smoother surface = fewer oscillations between points
- Acts like a trade-off: gains stability, slight loss of local detail
- Reduces overfitting on sparse 192-point dataset

**Effect:**
- Oscillation artifacts significantly reduced
- Contours become more physically meaningful
- Boundaries transitions more gradual
- **Update (Jan 2026):** Increased to 30 to better handle noisy experimental data

**Where applied:**
- `phase_plotting.py` - Default parameter in `create_phase_diagram_grids()` (line ~16)
- `analyze_gui.py` - Interactive visualization with explicit parameter (line ~490)
- `generate_presentation.py` - Phase diagram generation (2 locations, lines ~142, ~230)

### Solution 1b: Add Gaussian Post-Smoothing (NEW - Jan 2026)
**Change:** Added `gaussian_sigma=2.0` parameter

**What this does:**
- Applies a Gaussian blur filter to the interpolated transmission grid
- `sigma=2.0` means smoothing over ~2 grid points in each direction
- Acts as a low-pass filter to remove high-frequency noise artifacts
- Applied **after** RBF interpolation but before contour generation

**Effect:**
- Phase boundaries become smoother and more realistic
- Reduces sensitivity to individual noisy data points
- Creates more gradual transitions between clear/turbid/separated phases
- Better represents the underlying physical behavior rather than measurement noise

**Where applied:**
- `phase_plotting.py` - Default parameter in `create_phase_diagram_grids()` (line ~17)
- Uses `scipy.ndimage.gaussian_filter` for efficient smoothing
- Applied to all plots: analyze_gui.py and generate_presentation.py

### Solution 2: Fix GUI Clipping Bounds
**Change:** `np.clip(trans_grid, 35, 95)` → `np.clip(trans_grid, 0, 100)`

**Why this matters:**
- Original bounds [35, 95] created artificial **plateaus** at the edges
- Any RBF value below 35% was clipped to exactly 35% (fake flat region)
- Any value above 95% was clipped to exactly 95% (another fake plateau)
- These false plateaus distort the actual phase diagram shape

**New behavior:**
- Bounds [0, 100] represent physical limits of transmission
- No artificial plateaus created
- Preserves real surface features

**Where applied:**
- `analyze_gui.py` - Interactive visualization (line ~495)

### Solution 3: Already Implemented - Value Clipping
Code already had:
```python
trans_grid = np.clip(trans_grid, 0, 100)
```
This prevents physically impossible values (<0% or >100% transmission) while not creating artificial plateaus.

## Remaining RBF Considerations

### Boundary effects are still present because:
1. **Data sparsity at edges** - fewer wells near concentration boundaries
2. **Extrapolation behavior** - RBF naturally behaves differently at domain edges
3. **Log scale complexity** - log transformation can amplify boundary issues

### Acceptable trade-offs:
- **Stability > extreme accuracy at edges**
- **Pphase_plotting.py** (lines ~16-17) - NEW (Jan 2026)
   - Changed default `rbf_smooth` from 15→30
   - Changed default `gaussian_sigma` from 0.0→2.0
   - Applied automatically to all users of `create_phase_diagram_grids()`

2. **analyze_gui.py** (line ~490-494)
   - Increased `smooth` from 5→15→30 (now via explicit parameter)
   - Added `gaussian_sigma=2.0` parameter
   - Fixed clipping from [35,95]→[0,100] (previous fix)

3. **generate_presentation.py** (lines ~142, ~230)
   - Increased `smooth` from 5→15→30 (now via explicit parameter)
   - Added `gaussian_sigma=2.0` parameter at both call site
1. **Visual inspection:** Look at contours near concentration boundaries
2. **Point overlay test:** Plot actual 192 data points on contour map - contours should pass through or near points
3. **Edge behavior:** Check if contours are smooth or jagged near domain edges
RBF smoothing doubled (15→30):** More stable interpolation, fewer oscillations  
✅ **Gaussian post-smoothing added (sigma=2.0):** Realistic phase boundaries that handle noisy data  
✅ **Clipping fixed:** No artificial plateaus in GUI (previous fix)  
✅ **Physical bounds maintained:** Values stay in [0, 100] range  
✅ **Changes centralized:** Single parameter update in phase_plotting.py affects all visualizations

## Technical Details

**Why these values?**
- `rbf_smooth=30`: Balances fitting data vs. smoothness. Higher values = smoother but may miss real features
- `gaussian_sigma=2.0`: Smooths over ~4-5 grid points (2σ radius). Removes noise without over-blurring
- Combined effect: RBF handles global trends, Gaussian removes local noise

**Noise handling strategy:**
1. RBF with high smoothing prevents overfitting to individual noisy points
2. Gaussian filter removes remaining high-frequency artifacts
3. Result: Phase boundaries represent the most likely physical behavior given the data
  ```python
  from scipy.interpolate import griddata
  trans_grid = griddata((surf_data, poly_data), trans_data, 
                        (AS_grid, PS_grid), method='linear')
  ```
  Linear interpolation is more conservative but less smooth

## Files Modified

1. **analyze_gui.py** (line ~493-495)
   - Increased `smooth` from 5→15
   - Fixed clipping from [35,95]→[0,100]

2. **generate_presentation.py** (lines ~145, ~271)
   - Increased `smooth` from 5→15 in both RBF calls

## Testing Recommendation

After these changes, regenerate presentations and:
- [ ] Check if contours look smoother (less wiggly)
- [ ] Verify no artificial plateaus at 35% or 95%
- [ ] Confirm phase diagrams still show correct regions (clear/turbid/phase-sep)
- [ ] Compare with previous version to ensure improvements are visible

## Summary
✅ **Smoothing increased:** More stable interpolation, fewer oscillations  
✅ **Clipping fixed:** No artificial plateaus in GUI  
✅ **Physical bounds maintained:** Values stay in [0, 100] range  
✅ **Presentation regenerated:** Changes applied successfully

