#!/usr/bin/env python3
"""
Generate PowerPoint presentation for Rhamnolipid Analysis Report
Graph-heavy version with kinetics and transmission curves
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
import os
from datetime import datetime

# Constants
OUTPUT_DIR = 'analysis_output'
PHASE_DIAGRAM_DIR = 'analysis_output/rhamnolipid_phase_diagrams'
OUTPUT_FILE = 'Rhamnolipid_Analysis_v7.pptx'

# Colors
TITLE_COLOR = RGBColor(0, 51, 102)
ACCENT_COLOR = RGBColor(0, 112, 192)
TEXT_COLOR = RGBColor(51, 51, 51)


def add_title_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(9), Inches(1.5))
    p = title_box.text_frame.paragraphs[0]
    p.text = "Rhamnolipid Surfactant Analysis"
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = TITLE_COLOR
    p.alignment = PP_ALIGN.CENTER
    
    subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(4), Inches(9), Inches(1))
    p = subtitle_box.text_frame.paragraphs[0]
    p.text = "Polymer Interaction, Water Hardness & Kinetics\nShampoo Conditioning Applications"
    p.font.size = Pt(24)
    p.font.color.rgb = TEXT_COLOR
    p.alignment = PP_ALIGN.CENTER
    
    date_box = slide.shapes.add_textbox(Inches(0.5), Inches(5.5), Inches(9), Inches(0.5))
    p = date_box.text_frame.paragraphs[0]
    p.text = datetime.now().strftime("%B %d, %Y")
    p.font.size = Pt(16)
    p.font.color.rgb = TEXT_COLOR
    p.alignment = PP_ALIGN.CENTER


def add_section_title(prs, title):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(2.5), Inches(10), Inches(2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = ACCENT_COLOR
    shape.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.8), Inches(9), Inches(1.5))
    p = title_box.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.alignment = PP_ALIGN.CENTER


def add_image_slide(prs, title, image_path, caption=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(9), Inches(0.5))
    p = title_box.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = TITLE_COLOR
    
    if os.path.exists(image_path):
        slide.shapes.add_picture(image_path, Inches(0.3), Inches(0.7), width=Inches(9.4))
        
        if caption:
            caption_box = slide.shapes.add_textbox(Inches(0.5), Inches(7), Inches(9), Inches(0.4))
            p = caption_box.text_frame.paragraphs[0]
            p.text = caption
            p.font.size = Pt(11)
            p.font.italic = True
            p.font.color.rgb = TEXT_COLOR
            p.alignment = PP_ALIGN.CENTER


def add_two_image_slide(prs, title, image1_path, image2_path, label1="", label2=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(9), Inches(0.5))
    p = title_box.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = TITLE_COLOR
    
    if os.path.exists(image1_path):
        slide.shapes.add_picture(image1_path, Inches(0.15), Inches(0.7), width=Inches(4.85))
        if label1:
            lb = slide.shapes.add_textbox(Inches(0.15), Inches(5.7), Inches(4.85), Inches(0.35))
            p = lb.text_frame.paragraphs[0]
            p.text = label1
            p.font.size = Pt(11)
            p.alignment = PP_ALIGN.CENTER
            p.font.color.rgb = TEXT_COLOR
    
    if os.path.exists(image2_path):
        slide.shapes.add_picture(image2_path, Inches(5.05), Inches(0.7), width=Inches(4.85))
        if label2:
            lb = slide.shapes.add_textbox(Inches(5.05), Inches(5.7), Inches(4.85), Inches(0.35))
            p = lb.text_frame.paragraphs[0]
            p.text = label2
            p.font.size = Pt(11)
            p.alignment = PP_ALIGN.CENTER
            p.font.color.rgb = TEXT_COLOR


def add_brief_text_slide(prs, title, bullets):
    """Add slide with brief bullet points"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.7))
    p = title_box.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = TITLE_COLOR
    
    text_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(9), Inches(5.5))
    tf = text_box.text_frame
    tf.word_wrap = True
    
    for i, line in enumerate(bullets):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(18)
        p.font.color.rgb = TEXT_COLOR
        p.space_after = Pt(10)


def main():
    print("Creating PowerPoint presentation...")
    
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    
    # ========== TITLE ==========
    add_title_slide(prs)
    
    # ========== BRIEF SUMMARY ==========
    add_brief_text_slide(prs, "Key Findings", [
        "6 Conditioning Polymer Systems Evaluated with Rhamnolipid",
        "",
        "Water Hardness Tolerance Ranking (0 gpg → 7 gpg):",
        "• JR-30M (PQ-10 High): Best - no change (+1%)",
        "• DADMAC (PQ-6): Excellent - only 4% coacervation loss",
        "• AMT (PQ-76): Excellent - only 4% coacervation loss",
        "• KG-30M (PQ-10 Low): Good - 9% reduction",
        "• Excel Guar: Most Sensitive - 32% reduction in hard water",
        "",
        "Kinetics: All systems reach steady-state within 5-10 minutes",
        "Stability: All coacervates are kinetically stable (no re-dissolution)"
    ])
    
    # ========== SUMMARY METRICS ==========
    add_section_title(prs, "Summary Results")
    
    add_image_slide(prs, "Quantitative Metrics Summary",
                    os.path.join(OUTPUT_DIR, 'summary_metrics.png'))
    
    # ========== WATER HARDNESS EFFECT SECTION ==========
    add_section_title(prs, "Effect of Water Hardness on Rhamnolipid Systems")
    
    add_brief_text_slide(prs, "Water Hardness: Why It Matters", [
        "Hard water (Ca²⁺/Mg²⁺) competes with cationic polymers for:",
        "• Anionic rhamnolipid binding sites",
        "• Electrostatic interaction with hair/scalp",
        "",
        "Impact on Coacervate Formation:",
        "• Reduces polymer-surfactant complex formation",
        "• Can shift phase boundaries",
        "• Affects coacervate droplet size and stability",
        "",
        "Test Conditions:",
        "• 0 gpg (soft water): Deionized water control",
        "• 7 gpg (hard water): Typical US hard water level"
    ])
    
    add_two_image_slide(prs, "All Polymers - Soft vs Hard Water Comparison",
                        os.path.join(OUTPUT_DIR, 'polymer_comparison_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'polymer_comparison_7gpg.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    add_brief_text_slide(prs, "Water Hardness Impact by Polymer", [
        "JR-30M (PQ-10 High) - High Charge:",
        "  • Peak Abs: 3.8 → 3.8 (+1% in hard water) ✓ Best",
        "",
        "DADMAC (PQ-6) - Very High Charge:",
        "  • Peak Abs: 10.3 → 10.0 (-4% in hard water) ✓ Excellent",
        "",
        "AMT (PQ-76) - Medium-High Charge:",
        "  • Peak Abs: 5.4 → 5.2 (-4% in hard water) ✓ Excellent",
        "",
        "KG-30M (PQ-10 Low) - Low-Medium Charge:",
        "  • Peak Abs: 5.8 → 5.3 (-9% in hard water) ✓ Good",
        "",
        "Excel Guar - Low-Medium Charge:",
        "  • Peak Abs: 3.5 → 2.4 (-32% in hard water) ✗ Most Sensitive"
    ])
    
    # ========== KINETICS SECTION ==========
    add_section_title(prs, "Kinetics Analysis")
    
    add_image_slide(prs, "Formation Rate & Stability Comparison",
                    os.path.join(OUTPUT_DIR, 'kinetics_summary.png'),
                    "Lower time to 90% = faster formation; 100% stability = no dissolution")
    
    # ========== CROSS-POLYMER COMPARISON ==========
    add_section_title(prs, "Polymer Comparison")
    
    add_two_image_slide(prs, "Absorbance Curves - All Polymers",
                        os.path.join(OUTPUT_DIR, 'polymer_comparison_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'polymer_comparison_7gpg.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    # ========== BASELINE (No Polymer) ==========
    add_section_title(prs, "Baseline: No Polymer")
    
    add_image_slide(prs, "No Polymer - Hardness Comparison",
                    os.path.join(OUTPUT_DIR, 'hardness_comparison_NoPoly.png'))
    
    add_two_image_slide(prs, "No Polymer - Kinetics",
                        os.path.join(OUTPUT_DIR, 'kinetics_NoPoly_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'kinetics_NoPoly_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "No Polymer - Transmission Curves (Traditional View)",
                        os.path.join(OUTPUT_DIR, 'transmission_NoPoly_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'transmission_NoPoly_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    # ========== AMT ANALYSIS ==========
    add_section_title(prs, "AMT (PQ-76)")
    
    add_image_slide(prs, "AMT - Hardness Comparison",
                    os.path.join(OUTPUT_DIR, 'hardness_comparison_AMT.png'))
    
    # Phase diagrams (new - matching existing presentation style)
    add_image_slide(prs, "AMT - Phase Diagram Comparison",
                    os.path.join(PHASE_DIAGRAM_DIR, 'AMT_hardness_comparison.png'),
                    "Side-by-side phase diagrams showing coacervation regions at 0 vs 7 gpg")
    
    add_two_image_slide(prs, "AMT - Detailed Phase Diagrams",
                        os.path.join(PHASE_DIAGRAM_DIR, 'AMT_0gpg_phase_diagram.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'AMT_7gpg_phase_diagram.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    add_two_image_slide(prs, "AMT - Detailed Kinetics Analysis",
                        os.path.join(PHASE_DIAGRAM_DIR, 'AMT_0gpg_kinetics.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'AMT_7gpg_kinetics.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "AMT - Heatmaps",
                        os.path.join(OUTPUT_DIR, 'heatmap_AMT_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'heatmap_AMT_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "AMT - Kinetics",
                        os.path.join(OUTPUT_DIR, 'kinetics_AMT_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'kinetics_AMT_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "AMT - Transmission Curves",
                        os.path.join(OUTPUT_DIR, 'transmission_AMT_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'transmission_AMT_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    # ========== DADMAC ANALYSIS ==========
    add_section_title(prs, "DADMAC (PQ-6)")
    
    add_image_slide(prs, "DADMAC - Hardness Comparison",
                    os.path.join(OUTPUT_DIR, 'hardness_comparison_DADMAC.png'))
    
    # Phase diagrams (new - matching existing presentation style)
    add_image_slide(prs, "DADMAC - Phase Diagram Comparison",
                    os.path.join(PHASE_DIAGRAM_DIR, 'DADMAC_hardness_comparison.png'),
                    "Side-by-side phase diagrams showing coacervation regions at 0 vs 7 gpg")
    
    add_two_image_slide(prs, "DADMAC - Detailed Phase Diagrams",
                        os.path.join(PHASE_DIAGRAM_DIR, 'DADMAC_0gpg_phase_diagram.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'DADMAC_7gpg_phase_diagram.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    add_two_image_slide(prs, "DADMAC - Detailed Kinetics Analysis",
                        os.path.join(PHASE_DIAGRAM_DIR, 'DADMAC_0gpg_kinetics.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'DADMAC_7gpg_kinetics.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "DADMAC - Heatmaps",
                        os.path.join(OUTPUT_DIR, 'heatmap_DADMAC_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'heatmap_DADMAC_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "DADMAC - Kinetics",
                        os.path.join(OUTPUT_DIR, 'kinetics_DADMAC_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'kinetics_DADMAC_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "DADMAC - Transmission Curves",
                        os.path.join(OUTPUT_DIR, 'transmission_DADMAC_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'transmission_DADMAC_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    # ========== EXCEL GUAR ANALYSIS ==========
    add_section_title(prs, "Excel Guar")
    
    add_image_slide(prs, "Excel Guar - Hardness Comparison",
                    os.path.join(OUTPUT_DIR, 'hardness_comparison_Excel.png'))
    
    # Phase diagrams (new - matching existing presentation style)
    add_image_slide(prs, "Excel Guar - Phase Diagram Comparison",
                    os.path.join(PHASE_DIAGRAM_DIR, 'Excel_hardness_comparison.png'),
                    "Side-by-side phase diagrams showing coacervation regions at 0 vs 7 gpg")
    
    add_two_image_slide(prs, "Excel Guar - Detailed Phase Diagrams",
                        os.path.join(PHASE_DIAGRAM_DIR, 'Excel_0gpg_phase_diagram.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'Excel_7gpg_phase_diagram.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    add_two_image_slide(prs, "Excel Guar - Detailed Kinetics Analysis",
                        os.path.join(PHASE_DIAGRAM_DIR, 'Excel_0gpg_kinetics.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'Excel_7gpg_kinetics.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "Excel Guar - Heatmaps",
                        os.path.join(OUTPUT_DIR, 'heatmap_Excel_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'heatmap_Excel_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "Excel Guar - Kinetics",
                        os.path.join(OUTPUT_DIR, 'kinetics_Excel_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'kinetics_Excel_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "Excel Guar - Transmission Curves",
                        os.path.join(OUTPUT_DIR, 'transmission_Excel_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'transmission_Excel_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    # ========== JR-30M ANALYSIS (Now has both 0 and 7 gpg) ==========
    add_section_title(prs, "JR-30M (PQ-10 High Charge)")
    
    add_image_slide(prs, "JR-30M - Hardness Comparison",
                    os.path.join(OUTPUT_DIR, 'hardness_comparison_JR30M.png'))
    
    # Phase diagrams (new - matching existing presentation style)
    add_image_slide(prs, "JR-30M - Phase Diagram Comparison",
                    os.path.join(PHASE_DIAGRAM_DIR, 'JR30M_hardness_comparison.png'),
                    "Side-by-side phase diagrams showing coacervation regions at 0 vs 7 gpg")
    
    add_two_image_slide(prs, "JR-30M - Detailed Phase Diagrams",
                        os.path.join(PHASE_DIAGRAM_DIR, 'JR30M_0gpg_phase_diagram.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'JR30M_7gpg_phase_diagram.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    add_two_image_slide(prs, "JR-30M - Detailed Kinetics Analysis",
                        os.path.join(PHASE_DIAGRAM_DIR, 'JR30M_0gpg_kinetics.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'JR30M_7gpg_kinetics.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "JR-30M - Heatmaps",
                        os.path.join(OUTPUT_DIR, 'heatmap_JR30M_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'heatmap_JR30M_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "JR-30M - Kinetics",
                        os.path.join(OUTPUT_DIR, 'kinetics_JR30M_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'kinetics_JR30M_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "JR-30M - Transmission Curves",
                        os.path.join(OUTPUT_DIR, 'transmission_JR30M_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'transmission_JR30M_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    # ========== KG-30M ANALYSIS (Now has both 0 and 7 gpg) ==========
    add_section_title(prs, "KG-30M (PQ-10 Low Charge)")
    
    add_image_slide(prs, "KG-30M - Hardness Comparison",
                    os.path.join(OUTPUT_DIR, 'hardness_comparison_KG30M.png'))
    
    # Phase diagrams (new - matching existing presentation style)
    add_image_slide(prs, "KG-30M - Phase Diagram Comparison",
                    os.path.join(PHASE_DIAGRAM_DIR, 'KG30M_hardness_comparison.png'),
                    "Side-by-side phase diagrams showing coacervation regions at 0 vs 7 gpg")
    
    add_two_image_slide(prs, "KG-30M - Detailed Phase Diagrams",
                        os.path.join(PHASE_DIAGRAM_DIR, 'KG30M_0gpg_phase_diagram.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'KG30M_7gpg_phase_diagram.png'),
                        "0 gpg (Soft Water)",
                        "7 gpg (Hard Water)")
    
    add_two_image_slide(prs, "KG-30M - Detailed Kinetics Analysis",
                        os.path.join(PHASE_DIAGRAM_DIR, 'KG30M_0gpg_kinetics.png'),
                        os.path.join(PHASE_DIAGRAM_DIR, 'KG30M_7gpg_kinetics.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "KG-30M - Heatmaps",
                        os.path.join(OUTPUT_DIR, 'heatmap_KG30M_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'heatmap_KG30M_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "KG-30M - Kinetics",
                        os.path.join(OUTPUT_DIR, 'kinetics_KG30M_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'kinetics_KG30M_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    add_two_image_slide(prs, "KG-30M - Transmission Curves",
                        os.path.join(OUTPUT_DIR, 'transmission_KG30M_0gpg.png'),
                        os.path.join(OUTPUT_DIR, 'transmission_KG30M_7gpg.png'),
                        "0 gpg",
                        "7 gpg")
    
    # ========== CONCLUSIONS ==========
    add_section_title(prs, "Conclusions & Recommendations")
    
    add_brief_text_slide(prs, "Water Hardness Tolerance Summary", [
        "Ranking (Best to Worst for Hard Water Markets):",
        "",
        "1. JR-30M (PQ-10 High): +1% (unchanged) - Excellent",
        "   → Best choice for global markets with varying water quality",
        "",
        "2. DADMAC (PQ-6): -4% reduction - Excellent",
        "   → Highest absolute coacervation in both conditions",
        "",
        "3. AMT (PQ-76): -4% reduction - Excellent",
        "   → Good hardness tolerance despite medium-high charge",
        "",
        "4. KG-30M (PQ-10 Low): -9% reduction - Good",
        "   → Moderate sensitivity, still acceptable",
        "",
        "5. Excel Guar: -32% reduction - Most Sensitive",
        "   → Consider soft water positioning for this natural polymer"
    ])
    
    add_brief_text_slide(prs, "Kinetics & Stability Findings", [
        "Formation Kinetics:",
        "• All systems: Fast formation (<10 min to steady state)",
        "• DADMAC shows fastest coacervation initiation",
        "• No significant kinetic differences between hardness levels",
        "",
        "Coacervate Stability:",
        "• All systems: Stable coacervates (no re-dissolution)",
        "• 100% stability maintained over >60 minute observation",
        "• Hard water does not destabilize formed coacervates",
        "",
        "Phase Behavior:",
        "• Clear surfactant concentration thresholds for coacervation",
        "• Polymer concentration modulates transition sharpness",
        "• Hard water shifts phase boundaries to higher surfactant levels"
    ])
    
    add_brief_text_slide(prs, "Recommendations", [
        "For Broad Market Applicability:",
        "• DADMAC (PQ-6) - Highest coacervation + excellent hardness tolerance",
        "• JR-30M (PQ-10 High) - Best hardness tolerance overall",
        "• AMT (PQ-76) - Strong coacervation, excellent tolerance",
        "",
        "For Soft Water Premium Markets:",
        "• Excel Guar - Natural positioning (but hardness sensitive)",
        "",
        "For PQ-10 Cellulosic Positioning:",
        "• JR-30M preferred - better hardness tolerance than KG-30M",
        "",
        "Next Steps:",
        "• Deposition studies on hair substrates",
        "• Full shampoo formula compatibility testing",
        "• Consumer sensory evaluation"
    ])
    
    # Save presentation
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    prs.save(output_path)
    print(f"\nPresentation saved to: {output_path}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == '__main__':
    main()
