
import math
from triage_questions import get_questions


class TriageSession:
    def __init__(self, emergency_type, initial_answers=None, adaptive=False):
        self.emergency_type = emergency_type
        self.questions = get_questions(emergency_type)
        self.answers = dict(initial_answers or {})
        self.current_index = 0
        self.is_adaptive = bool(adaptive)

        # Adaptive sessions skip questions whose answers are already known.
        if self.is_adaptive:
            self._skip_answered_questions()

    @staticmethod
    def _is_known(value):
        if value is None:
            return False

        if isinstance(value, str):
            return value.strip().lower() not in {
                "", "nan", "null"
            }

        if isinstance(value, float) and math.isnan(value):
            return False

        return True

    def _skip_answered_questions(self):
        while self.current_index < len(self.questions):
            question = self.questions[self.current_index]
            feature = question.get("feature")

            if feature and self._is_known(self.answers.get(feature)):
                self.current_index += 1
            else:
                break

    def get_current_question(self):
        if self.current_index >= len(self.questions):
            return None

        return self.questions[self.current_index]

    def answer_question(self, answer):
        question = self.get_current_question()

        if question is None:
            return False

        feature = question.get("feature")

        if not feature:
            return False

        self.answers[feature] = answer
        self.current_index += 1

        # Skip any subsequent questions already answered by extraction.
        if self.is_adaptive:
            self._skip_answered_questions()

        return True

    def is_complete(self):
        return self.current_index >= len(self.questions)

    def get_result_data(self):
        return dict(self.answers)
