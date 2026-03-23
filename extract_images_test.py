"""
读取学生作业的PDF和 mark scheme 的docx文件

输出每个文档中的图片

"""
import pdf2image
from PIL import Image
from docx import Document
import io

SOURCE_STUDENT="student_homework"
SOURCE_TEACHER="mark_scheme"


class ImageAsset:
    def __init__(self,image,image_index,source):
        self.image=image
        self.image_index=image_index
        self.source=source

def load_teacher_word_document(mark_scheme_path):
    results=[]
    doc = Document(mark_scheme_path)
    is_solution=False
    image_index=1
    for paragraph in doc.paragraphs:
        text=paragraph.text.strip().lower()
        if not is_solution:
            if "solution" in text:
                is_solution=True
                continue
        if is_solution:
            for run in paragraph.runs:
                if run.element.xpath(".//w:drawing"):
                    drawing = run.element.xpath(".//w:drawing")[0]
                    blip = drawing.xpath(".//a:blip")[0]
                    r_id = blip.attrib[
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                    ]
                    image_part = doc.part.related_parts[r_id]
                    image_bytes = image_part.blob
                    image = Image.open(io.BytesIO(image_bytes)).convert("L")
                    results.append(ImageAsset(image, image_index, SOURCE_TEACHER))
                    image_index += 1
    return results


def load_student_pdf(path):
    pages = []
    images = pdf2image.convert_from_path(path)
    for i, image in enumerate(images):
        image = image.convert("L")
        pages.append(ImageAsset(image,i+1,SOURCE_STUDENT))
    return pages







