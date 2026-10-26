"""Extract slide contents from phase_diagrams_presentation.pptx"""
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
import os

# Use full path
base_dir = r'c:\Users\gamsky.cj\OneDrive - Procter and Gamble\! P&G Data\Post-2023 Reorganization\Surfactant Phase Diagrams\phase_diagram_database'
pptx_path = os.path.join(base_dir, 'temp_pres.pptx')
prs = Presentation(pptx_path)
print(f'Total slides: {len(prs.slides)}')
print('=' * 60)

for i, slide in enumerate(prs.slides, 1):
    title = ''
    image_count = 0
    text_content = []
    
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                txt = para.text.strip()
                if txt:
                    if not title and shape.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER:
                        title = txt
                    else:
                        text_content.append(txt[:100])
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            image_count += 1
    
    no_title = '(no title)'
    print(f'Slide {i}: {title[:60] if title else no_title}')
    if image_count:
        print(f'  Images: {image_count}')
    if text_content:
        for t in text_content[:5]:
            print(f'  - {t}')
    print()
