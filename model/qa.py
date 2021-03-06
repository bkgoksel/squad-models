"""
Module that encapsulates the objects to represent contexts, questions and
answers at various points of existence.
"""
import numpy as np
import bisect
from typing import cast, List, Any, Set, NewType, Dict

from model.text_processor import TextProcessor
from model.tokenizer import Token, Tokenizer


QuestionId = NewType("QuestionId", str)


class Processed:
    """
    Base Class for any object that stores processed and tokenized text
    """

    tokens: List[Token]
    original_text: str
    text: str

    def __init__(
        self, text: str, tokenizer: Tokenizer, processor: TextProcessor
    ) -> None:
        self.original_text = text
        self.text = processor.process(text)
        self.tokens = tokenizer.tokenize(self.text)
        assert len(self.text) > 0, "Textual object with empty text"
        assert len(self.tokens) > 0, "Tokenized object with no tokensj"

    def __eq__(self, other: Any) -> bool:
        return cast(
            bool,
            self.original_text == other.original_text
            and self.text == other.text
            and self.tokens == other.tokens,
        )


class Answer(Processed):
    """
    Base class for an Answer, stores the text and span boundaries
    """

    text: str
    span_start: int
    span_end: int

    def __init__(
        self, text: str, span_start: int, tokenizer: Tokenizer, processor: TextProcessor
    ) -> None:
        super().__init__(text, tokenizer, processor)
        self.span_start = span_start
        self.span_end = self.span_start + len(self.text)

    def __eq__(self, other: Any) -> bool:
        """
        Two answers are equal if their spans and text are equal
        """
        return (
            super().__eq__(other)
            and self.span_start == other.span_start
            and self.span_end == other.span_end
        )

    def __hash__(self) -> Any:
        """
        Use the answer components to hash the answer
        """
        return hash("%d_%d_%s" % (self.span_start, self.span_end, self.text))


class QuestionAnswer(Processed):
    """
    Base class for a question paired with its answer.
    Stores the question text and a list of answers
    """

    question_id: QuestionId
    answers: Set[Answer]

    def __init__(
        self,
        question_id: str,
        text: str,
        answers: Set[Answer],
        tokenizer: Tokenizer,
        processor: TextProcessor,
    ) -> None:
        self.question_id = cast(QuestionId, question_id)
        self.answers = answers
        super().__init__(text, tokenizer, processor)

    def __eq__(self, other: Any) -> bool:
        return (
            super().__eq__(other)
            and self.answers == other.answers
            and self.question_id == other.question_id
        )


class ContextQuestionAnswer(Processed):
    """
    Base class for a context paragraph and its question-answer pairs
    Stores the context text and a list of question answer pair objects
    """

    qas: List[QuestionAnswer]

    def __init__(
        self,
        text: str,
        qas: List[QuestionAnswer],
        tokenizer: Tokenizer,
        processor: TextProcessor,
    ) -> None:
        self.qas = qas
        super().__init__(text, tokenizer, processor)

    def __eq__(self, other: Any) -> bool:
        return super().__eq__(other) and self.qas == other.qas


class EncodedAnswer:
    """
    Class to store an Answer's encoding
        - span_start: int mapping to the first context token that's part of the answer
        - span_end: int mapping to the last context token that's part of the answer
    """

    span_start: int
    span_end: int

    def __init__(self, answer: Answer, context_tokens: List[Token]) -> None:
        """
        We have List[Token]:
            (word=word, span=(start, end))
        """
        spans = [tok.span for tok in context_tokens]
        token_starts, token_ends = zip(*spans)
        self.span_start = bisect.bisect_right(token_starts, answer.span_start) - 1
        self.span_end = bisect.bisect_left(token_ends, answer.span_end)

    def __eq__(self, other: Any) -> bool:
        """
        Two answers are equal if their spans and text are equal
        """
        return cast(
            bool,
            self.span_start == other.span_start and self.span_end == other.span_end,
        )


class EncodedQuestionAnswer:
    """
    Class for a Question's encoding
    Paired with its encoded answers
    """

    question_id: QuestionId
    word_encoding: Any  # numpy array
    char_encoding: List[Any]  # numpy array
    answers: List[EncodedAnswer]

    def __init__(
        self,
        qa: QuestionAnswer,
        token_mapping: Dict[str, int],
        char_mapping: Dict[str, int],
        context_tokens: List[Token],
    ) -> None:
        self.question_id = qa.question_id
        self.word_encoding = np.array(
            [token_mapping.get(tk.word, 1) for tk in qa.tokens]
        )
        self.char_encoding = [
            np.array([char_mapping.get(char, 1) for char in tk.word])
            for tk in qa.tokens
        ]
        self.answers = [EncodedAnswer(ans, context_tokens) for ans in qa.answers]

    def __eq__(self, other: Any) -> bool:
        return cast(
            bool,
            (
                self.question_id == other.question_id
                and np.all(self.word_encoding == other.word_encoding)
                and np.all(self.char_encoding == other.char_encoding)
                and self.answers == other.answers
            ),
        )


class EncodedContextQuestionAnswer:
    """
    Class for a context paragraph and its question-answer pairs
    Stores them in encoded form
    """

    word_encoding: Any  # numpy array
    char_encoding: List[Any]  # numpy array
    qas: List[EncodedQuestionAnswer]

    def __init__(
        self,
        ctx: ContextQuestionAnswer,
        token_mapping: Dict[str, int],
        char_mapping: Dict[str, int],
    ) -> None:
        self.word_encoding = np.array(
            [token_mapping.get(tk.word, 1) for tk in ctx.tokens]
        )
        self.char_encoding = [
            np.array([char_mapping.get(char, 1) for char in tk.word])
            for tk in ctx.tokens
        ]
        self.qas = [
            EncodedQuestionAnswer(qa, token_mapping, char_mapping, ctx.tokens)
            for qa in ctx.qas
        ]

    def __eq__(self, other: Any) -> bool:
        return cast(
            bool,
            (
                self.qas == other.qas
                and np.all(self.char_encoding == other.char_encoding)
                and np.all(self.word_encoding == other.word_encoding)
            ),
        )


class EncodedSample:
    """
    Stores a single model sample (context, question, answers)
        - span_starts and span_ends are the same shape as
            context and are 1 at each valid start/end index
    """

    question_id: QuestionId
    question_words: Any  # numpy array
    question_chars: List[Any]  # numpy array
    context_words: Any  # numpy array
    context_chars: List[Any]  # numpy array
    has_answer: bool
    span_starts: Any  # numpy array
    span_ends: Any  # numpy array

    def __init__(
        self, ctx_word_encoding: Any, ctx_char_encoding: Any, qa: EncodedQuestionAnswer
    ) -> None:
        self.question_id = qa.question_id
        self.context_words = ctx_word_encoding
        self.context_chars = ctx_char_encoding
        self.question_words = qa.word_encoding
        self.question_chars = qa.char_encoding
        self.has_answer = bool(qa.answers)
        self.span_starts = np.zeros_like(self.context_words)
        self.span_ends = np.zeros_like(self.context_words)
        if self.has_answer:
            starts = np.array([ans.span_start for ans in qa.answers])
            ends = np.array([ans.span_end for ans in qa.answers])
            self.span_starts[starts] = 1
            self.span_ends[ends] = 1

    def __eq__(self, other: Any) -> bool:
        return cast(
            bool,
            (
                self.question_id == other.question_id
                and np.all(self.context_words == other.context_words)
                and np.all(self.question_words == other.question_words)
                and np.all(self.context_chars == other.context_chars)
                and np.all(self.question_chars == other.question_chars)
                and self.has_answer == other.has_answer
                and np.all(self.span_starts == other.span_starts)
                and np.all(self.span_ends == other.span_ends)
            ),
        )
