import re
from models.course import Course


def clean_text(text: str) -> str:
    """HTML 태그 제거, 공백 정리, 특수문자 정제"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)      # HTML 태그 제거
    text = re.sub(r"&[a-z]+;", " ", text)    # HTML 엔티티 제거
    text = re.sub(r"\s+", " ", text)         # 연속 공백 정리
    return text.strip()


def clean_course(course: Course) -> Course:
    """강좌 텍스트 필드 전체 정제"""
    course.title = clean_text(course.title)
    course.institution = clean_text(course.institution)
    course.description = clean_text(course.description)
    course.duration = clean_text(course.duration)
    return course