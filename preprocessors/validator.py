from models.course import Course

MIN_TITLE_LENGTH = 2
MIN_DESCRIPTION_LENGTH = 20


def is_valid(course: Course) -> bool:
    """유효하지 않은 강좌 필터링"""
    if not course.title or len(course.title) < MIN_TITLE_LENGTH:
        return False
    if not course.url:
        return False
    if not course.id:
        return False
    if course.platform != "온국민평생배움터":
        if len(course.description) < MIN_DESCRIPTION_LENGTH:
            return False
    return True