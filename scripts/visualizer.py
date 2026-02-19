
import matplotlib.pyplot as plt
from mplsoccer import PyPizza, Radar, FontManager
import os

# Use default fonts to avoid download errors
font_normal = None
font_bold = None

def create_pizza_chart(player_name, stats, percentiles, output_dir='output_charts'):
    """
    Create a Pizza Chart for a player.
    stats: list of values
    percentiles: list of percentile values (0-100)
    params: list of parameter names
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    params = [
        "Non-Penalty Goals", "xG", "Shots", "Assists", "SCA", 
        "Passes %", "Prog. Passes", "Prog. Carries", 
        "Tackles", "Interceptions", "Aerials Won", "Clearances"
    ]
    
    # Slice colors based on categories (Attack, Poss, Def)
    slice_colors = ["#1A78CF"] * 5 + ["#FF9300"] * 3 + ["#D70232"] * 4
    text_colors = ["#000000"] * 8 + ["#F2F2F2"] * 4
    
    baker = PyPizza(
        params=params,                  # list of parameters
        background_color="#EBEBE9",     # background color
        straight_line_color="#222222",  # color for straight lines
        straight_line_lw=1,             # linewidth for straight lines
        last_circle_lw=1,               # linewidth of last circle
        last_circle_color="#222222",    # color of last circle
        other_circle_ls="-.",           # linestyle for other circles
        other_circle_lw=1               # linewidth for other circles
    )
    
    fig, ax = baker.make_pizza(
        percentiles,              # list of values
        figsize=(8, 8),      # adjust figsize according to your need
        slice_colors=slice_colors,
        value_colors=text_colors,
        value_bck_colors=slice_colors,
        kwargs_slices=dict(
            facecolor="cornflowerblue", edgecolor="#222222",
            zorder=2, linewidth=1
        ),
        kwargs_params=dict(
            color="#000000", fontsize=10,
            va="center"
        ),
        kwargs_values=dict(
            color="#000000", fontsize=10,
            zorder=3,
            bbox=dict(
                edgecolor="#000000", facecolor="cornflowerblue",
                boxstyle="round,pad=0.2", lw=1
            )
        )
    )
    
    # Add title
    fig.text(
        0.515, 0.97, f"{player_name} - Style Profile", size=18,
        ha="center", color="#000000"
    )
    
    # Save
    clean_name = "".join(x for x in player_name if x.isalnum() or x in " -_")
    filename = f"{output_dir}/{clean_name}_pizza.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    return filename

def create_comparison_chart(team1_name, team2_name, labels, team1_values, team2_values, output_dir='output_charts'):
    """
    Create a horizontal bar chart comparing two teams (Butterfly Chart).
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    y = range(len(labels))
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Team 1 bars (Negative to go left)
    ax.barh(y, [-v for v in team1_values], color='skyblue', label=team1_name)
    # Team 2 bars (Positive to go right)
    ax.barh(y, team2_values, color='salmon', label=team2_name)
    
    # Labels in the middle
    for i, label in enumerate(labels):
        ax.text(0, i, label, ha='center', va='center', fontweight='bold')
        
        # Value labels
        ax.text(-team1_values[i]-0.5, i, str(round(team1_values[i], 1)), ha='right', va='center')
        ax.text(team2_values[i]+0.5, i, str(round(team2_values[i], 1)), ha='left', va='center')
        
    ax.set_yticks([])
    ax.set_xticks([]) # Hide x axis numbers
    
    # Legend
    ax.legend(loc='upper right')
    
    plt.title(f"Head-to-Head: {team1_name} vs {team2_name}")
    
    filename = f"{output_dir}/{team1_name}_vs_{team2_name}_comparison.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    return filename
