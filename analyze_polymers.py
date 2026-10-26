import sqlite3
import pandas as pd
import numpy as np

# Connect to database
conn = sqlite3.connect('phase_diagrams.db')

# Get all experiments with their equilibrium data
query = """
    SELECT 
        experiment_id,
        polymer_name,
        surfactant_name,
        timepoint_minutes,
        transmission_pct,
        surfactant_pct,
        polymer_pct
    FROM measurements
    ORDER BY polymer_name, surfactant_name, experiment_id, timepoint_minutes
"""

data = pd.read_sql_query(query, conn)
conn.close()

print("="*80)
print("POLYMER COACERVATION ANALYSIS")
print("="*80)

# Group by polymer and analyze
for polymer_name in sorted(data['polymer_name'].unique()):
    polymer_data = data[data['polymer_name'] == polymer_name]
    
    print(f"\n{'='*80}")
    print(f"POLYMER: {polymer_name}")
    print(f"{'='*80}")
    
    # Get equilibrium data (latest timepoint per experiment)
    eq_indices = polymer_data.groupby('experiment_id')['timepoint_minutes'].idxmax()
    eq_data = polymer_data.loc[eq_indices].reset_index(drop=True)
    
    # Analyze by surfactant
    surfactant_stats = []
    for surf_name in sorted(polymer_data['surfactant_name'].unique()):
        surf_eq_data = eq_data[eq_data['surfactant_name'] == surf_name]
        
        if len(surf_eq_data) == 0:
            continue
        
        # Phase behavior classification (at equilibrium, 75% threshold)
        clear = len(surf_eq_data[surf_eq_data['transmission_pct'] >= 75])
        precipitate = len(surf_eq_data[surf_eq_data['transmission_pct'] < 75])
        total = len(surf_eq_data)
        
        clear_pct = 100 * clear / total if total > 0 else 0
        precipitate_pct = 100 * precipitate / total if total > 0 else 0
        
        # Concentration ranges
        surf_min, surf_max = surf_eq_data['surfactant_pct'].min(), surf_eq_data['surfactant_pct'].max()
        poly_min, poly_max = surf_eq_data['polymer_pct'].min(), surf_eq_data['polymer_pct'].max()
        
        # Get kinetic data for equilibration time - aggregate by timepoint first
        surf_experiments = surf_eq_data['experiment_id'].unique()
        
        eq_times = []
        for exp_id in surf_experiments:
            exp_kinetic = polymer_data[polymer_data['experiment_id'] == exp_id].sort_values('timepoint_minutes')
            
            if len(exp_kinetic) > 1:
                # Average transmission across ALL wells at each timepoint
                timepoint_stats = exp_kinetic.groupby('timepoint_minutes')['transmission_pct'].mean()
                
                # Get final average transmission
                final_avg = timepoint_stats.iloc[-1]
                
                # Find first timepoint where transmission >= 98% of final
                threshold_98 = final_avg * 0.98
                eq_mask = timepoint_stats >= threshold_98
                
                if eq_mask.any():
                    eq_time = timepoint_stats[eq_mask].index[0]
                    eq_times.append(eq_time)
        
        avg_eq_time = np.mean(eq_times) if eq_times else None
        std_eq_time = np.std(eq_times) if len(eq_times) > 1 else None
        
        surfactant_stats.append({
            'surfactant': surf_name,
            'clear_pct': clear_pct,
            'turbid_pct': turbid_pct,
            'phase_sep_pct': phase_sep_pct,
            'eq_time': avg_eq_time,
            'eq_time_std': std_eq_time,
            'eq_time_values': eq_times,
            'trans_avg': surf_eq_data['transmission_pct'].mean(),
            'n_wells': total,
            'surf_range': (surf_min, surf_max),
            'poly_range': (poly_min, poly_max)
        })
    
    # Rank by coacervation
    surfactant_stats = sorted(surfactant_stats, key=lambda x: x['phase_sep_pct'], reverse=True)
    
    print(f"\nNumber of surfactants tested: {len(surfactant_stats)}")
    print(f"\nCoacervation Ranking (by phase-separation %):")
    print("-" * 80)
    
    for i, stats in enumerate(surfactant_stats, 1):
        print(f"\n{i}. {stats['surfactant']}:")
        print(f"   Phase-separated: {stats['phase_sep_pct']:.1f}%  |  Turbid: {stats['turbid_pct']:.1f}%  |  Clear: {stats['clear_pct']:.1f}%")
        if stats['eq_time']:
            if stats['eq_time_std']:
                print(f"   Equilibration time: {stats['eq_time']:.2f} ± {stats['eq_time_std']:.2f} min (range: {min(stats['eq_time_values']):.2f}-{max(stats['eq_time_values']):.2f})")
            else:
                print(f"   Equilibration time: {stats['eq_time']:.2f} min")
        else:
            print(f"   Equilibration time: N/A")
        print(f"   Mean transmission: {stats['trans_avg']:.1f}%")
        print(f"   Surfactant tested: {stats['surf_range'][0]:.4f}% - {stats['surf_range'][1]:.4f}%")
        print(f"   Polymer tested: {stats['poly_range'][0]:.6f}% - {stats['poly_range'][1]:.4f}%")
    
    # Overall conclusion for polymer
    print(f"\n{'-'*80}")
    print("CONCLUSIONS:")
    print("-" * 80)
    
    avg_phase_sep = np.mean([s['phase_sep_pct'] for s in surfactant_stats])
    eq_times_all = []
    for s in surfactant_stats:
        if s['eq_time'] is not None:
            eq_times_all.append(s['eq_time'])
    
    avg_eq_time = np.mean(eq_times_all) if eq_times_all else None
    
    print(f"\nAverage coacervation potential: {avg_phase_sep:.1f}% phase-separated")
    if avg_eq_time:
        print(f"Average equilibration time: {avg_eq_time:.2f} minutes")
    
    # Summarize coacervation behavior
    best_coarc = surfactant_stats[0]
    worst_coarc = surfactant_stats[-1]
    
    print(f"\n• Best coacervation: {best_coarc['surfactant']} ({best_coarc['phase_sep_pct']:.1f}% phase-sep)")
    print(f"• Poorest coacervation: {worst_coarc['surfactant']} ({worst_coarc['phase_sep_pct']:.1f}% phase-sep)")
    
    # Kinetics
    eq_stats_valid = [s for s in surfactant_stats if s['eq_time'] is not None]
    if eq_stats_valid:
        fastest = min(eq_stats_valid, key=lambda x: x['eq_time'])
        slowest = max(eq_stats_valid, key=lambda x: x['eq_time'])
        
        print(f"• Fastest equilibration: {fastest['surfactant']} ({fastest['eq_time']:.2f} min)")
        print(f"• Slowest equilibration: {slowest['surfactant']} ({slowest['eq_time']:.2f} min)")
        
        # Check kinetic variation
        kinetic_variation = np.std([s['eq_time'] for s in eq_stats_valid])
        if kinetic_variation > 10:
            print(f"\n  *** HIGH KINETIC VARIATION (sigma = {kinetic_variation:.1f} min) ***")
            print(f"      Significant differences in equilibration speeds across surfactants!")
    
    # Classification
    if avg_phase_sep > 50:
        behavior = "STRONG COACERVATION - excellent for material deposition"
    elif avg_phase_sep > 30:
        behavior = "MODERATE COACERVATION - good coacervation in select regions"
    else:
        behavior = "WEAK COACERVATION - limited phase separation"
    
    print(f"\nClassification: {behavior}")
    
    # Additional insights
    turbid_systems = [s for s in surfactant_stats if s['turbid_pct'] > 30]
    if turbid_systems:
        print(f"\n• Notable turbidity ({len(turbid_systems)} surfactants show >30% turbid):")
        for ts in turbid_systems:
            print(f"  - {ts['surfactant']}: {ts['turbid_pct']:.0f}% turbid")

print(f"\n{'='*80}\n")

