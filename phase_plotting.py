"""
Shared phase diagram plotting functions for GUI and presentation generation.
Ensures consistent visualization across both interfaces.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
from scipy.interpolate import Rbf, griddata
from scipy.ndimage import gaussian_filter
try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF as GPKernel, WhiteKernel
    GP_AVAILABLE = True
except ImportError:
    GP_AVAILABLE = False


def create_phase_diagram_grids(data, n_points=400, method='griddata',
                               rbf_function='multiquadric', rbf_smooth=30,
                               gaussian_sigma=1.5, gp_length_scale=0.1):
    """
    Create log-spaced grids and interpolate transmission values.

    Args:
        data: DataFrame with surfactant_pct, polymer_pct, transmission_pct columns
        n_points: Grid resolution (default 400)
        method: 'griddata' (default, conservative), 'rbf', or 'gp' (Gaussian Process)
        rbf_function: RBF kernel to use when method='rbf'
        rbf_smooth: RBF smoothing parameter (default 30, higher = smoother boundaries)
        gaussian_sigma: if >0, apply Gaussian smoothing on the interpolated grid (default 1.5)
        gp_length_scale: Length scale for GP kernel (default 0.1, controls smoothness)

    Returns:
        tuple: (AS_grid, PS_grid, trans_grid)
    """
    ps_min, ps_max = data['polymer_pct'].min(), data['polymer_pct'].max()
    as_min, as_max = data['surfactant_pct'].min(), data['surfactant_pct'].max()

    ps_grid = np.logspace(np.log10(ps_min), np.log10(ps_max), n_points)
    as_grid = np.logspace(np.log10(as_min), np.log10(as_max), n_points)
    AS_grid, PS_grid = np.meshgrid(as_grid, ps_grid)

    if method == 'rbf':
        # RBF interpolation; smoothing regularizes small-scale wiggles
        rbf = Rbf(data['surfactant_pct'], data['polymer_pct'], data['transmission_pct'],
                  function=rbf_function, smooth=rbf_smooth)
        trans_grid = rbf(AS_grid, PS_grid)
    elif method == 'gp':
        # Gaussian Process: probabilistic interpolation with uncertainty
        if not GP_AVAILABLE:
            raise ImportError("scikit-learn required for GP method. Install: pip install scikit-learn")
        
        # Work in log space for better scaling
        X_train = np.log10(np.vstack((data['surfactant_pct'], data['polymer_pct'])).T)
        y_train = data['transmission_pct'].values
        
        # GP kernel: RBF (smoothness) + WhiteKernel (noise)
        # Fix length_scale bounds to prevent optimizer from overriding
        kernel = GPKernel(length_scale=gp_length_scale, length_scale_bounds='fixed') + \
                 WhiteKernel(noise_level=1.0, noise_level_bounds=(0.1, 10.0))
        
        gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=5, alpha=0.0, normalize_y=True)
        gp.fit(X_train, y_train)
        
        # Predict on log-scale grid
        X_grid = np.log10(np.vstack([AS_grid.ravel(), PS_grid.ravel()]).T)
        trans_pred, trans_std = gp.predict(X_grid, return_std=True)
        trans_grid = trans_pred.reshape(AS_grid.shape)
    else:
        # griddata linear: most conservative, only interpolates within convex hull
        pts = np.vstack((data['surfactant_pct'], data['polymer_pct'])).T
        vals = data['transmission_pct'].values
        trans_grid = griddata(pts, vals, (AS_grid, PS_grid), method='linear')
        # Fill holes (outside convex hull) using nearest neighbor
        if np.any(np.isnan(trans_grid)):
            trans_grid_nn = griddata(pts, vals, (AS_grid, PS_grid), method='nearest')
            trans_grid = np.where(np.isnan(trans_grid), trans_grid_nn, trans_grid)

    # Optional smoothing in grid index space
    if gaussian_sigma and gaussian_sigma > 0.0:
        print(f"Applying Gaussian smoothing with sigma={gaussian_sigma}")
        trans_grid = gaussian_filter(trans_grid, sigma=gaussian_sigma, mode='nearest')
    
    print(f"Interpolation complete: method={method}, n_points={n_points}, grid shape={trans_grid.shape}")

    trans_grid = np.clip(trans_grid, 35, 95)

    return AS_grid, PS_grid, trans_grid


def plot_continuous_map(ax, AS_grid, PS_grid, trans_grid, data, threshold, 
                        surfactant, polymer, fg_color='black', bg_light='white', 
                        fig=None):
    """Plot continuous transmission map with contour lines."""
    # Contour levels — shared 0-100% transmission scale
    contourf_levels = np.linspace(0, 100, 21)
    contourf = ax.contourf(AS_grid, PS_grid, trans_grid, levels=contourf_levels, 
                           cmap='RdYlGn', alpha=0.85, vmin=0, vmax=100, extend='both')
    
    contour_lines = ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                               colors='black', linewidths=2.0, linestyles='-',
                               antialiased=True)
    
    scatter = ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                       c=data['transmission_pct'], s=15, cmap='RdYlGn',
                       edgecolors='black', linewidth=0.3, alpha=0.6, vmin=0, vmax=100)
    
    ax.set_xlabel(f'{surfactant} concentration (%)', fontsize=10, fontweight='bold')
    ax.set_ylabel(f'{polymer} concentration (%)', fontsize=10, fontweight='bold')
    ax.set_title('Continuous Transmission Map', fontsize=11, fontweight='bold')
    ax.set_xscale('log')
    ax.set_yscale('log')
    # Tight limits to the measured range (like the reference figures)
    try:
        ax.set_xlim(float(data['surfactant_pct'].min()), float(data['surfactant_pct'].max()))
        ax.set_ylim(float(data['polymer_pct'].min()), float(data['polymer_pct'].max()))
    except Exception:  # noqa: BLE001
        pass
    
    # Tick locations
    x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    
    ax.xaxis.set_major_locator(FixedLocator(x_ticks))
    ax.yaxis.set_major_locator(FixedLocator(y_ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_minor_formatter(NullFormatter())
    
    ax.grid(True, alpha=0.3, which='both')
    ax.minorticks_on()
    
    if fig is not None:
        cbar = fig.colorbar(contourf, ax=ax)
        cbar.set_label('Transmission (%)')
    
    return scatter


def plot_binary_boundary(ax, AS_grid, PS_grid, trans_grid, data, threshold,
                        surfactant, polymer, fg_color='black', bg_light='white',
                        fig=None):
    """Plot binary phase boundary with scatter points."""
    colors = ['#e74c3c' if t < threshold else '#2ecc71' for t in data['transmission_pct']]
    scatter = ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                        c=colors, s=50, edgecolors='black', linewidth=0.5, alpha=0.8)
    
    # Smooth contour with anti-aliasing
    contour_thresh = ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                                colors='black', linewidths=2.0, antialiased=True)
    # Add filled contour bands for clarity
    ax.contourf(AS_grid, PS_grid, trans_grid, levels=[35, threshold, 95],
               colors=['#e74c3c', '#2ecc71'], alpha=0.15, antialiased=True)
    
    ax.set_xlabel(f'{surfactant} concentration (%)', fontsize=10, fontweight='bold')
    ax.set_ylabel(f'{polymer} concentration (%)', fontsize=10, fontweight='bold')
    ax.set_title(f'Binary Phase Boundary ({threshold:.0f}% Threshold)', fontsize=11, fontweight='bold')
    ax.set_xscale('log')
    ax.set_yscale('log')
    # Tight limits to the measured range (like the reference figures)
    try:
        ax.set_xlim(float(data['surfactant_pct'].min()), float(data['surfactant_pct'].max()))
        ax.set_ylim(float(data['polymer_pct'].min()), float(data['polymer_pct'].max()))
    except Exception:  # noqa: BLE001
        pass
    
    # Tick locations
    x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    
    ax.xaxis.set_major_locator(FixedLocator(x_ticks))
    ax.yaxis.set_major_locator(FixedLocator(y_ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_minor_formatter(NullFormatter())
    
    ax.grid(True, alpha=0.3, which='both')
    ax.minorticks_on()
    
    # Legend
    red_patch = mpatches.Patch(color='#e74c3c', label=f'Precipitate (<{threshold:.0f}%)')
    green_patch = mpatches.Patch(color='#2ecc71', label=f'Clear (≥{threshold:.0f}%)')
    ax.legend(handles=[red_patch, green_patch], loc='upper left', fontsize=8)
    
    return scatter
