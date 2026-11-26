"""Pronounce printed dollar amounts without changing their exact values."""
import re

SMALL = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
AMOUNT = re.compile(r"(?<![\w$])\$(\d{1,4})(?:\.(\d{2}))?(?!\d|,\d|\.\d)")


def number(n):
    if n < 20:
        return SMALL[n]
    if n < 100:
        whole, rest = divmod(n, 10)
        return TENS[whole] + (" " + SMALL[rest] if rest else "")
    divisor, unit = (100, "hundred") if n < 1000 else (1000, "thousand")
    whole, rest = divmod(n, divisor)
    return number(whole) + " " + unit + (" " + number(rest) if rest else "")


def spoken_money(text):
    def replace(match):
        dollars = int(match[1])
        cents = int(match[2] or 0)
        main = number(dollars) + (" dollar" if dollars == 1 else " dollars")
        if not cents:
            return main
        change = number(cents) + (" cent" if cents == 1 else " cents")
        return main + " and " + change if dollars else change
    return AMOUNT.sub(replace, text)


def normalize_story_money(story):
    for utterance in story["script"]:
        utterance["text"] = spoken_money(utterance["text"])
    for beat in story["beats"]:
        cue = beat["cue"]
        if "phrase" in cue:
            cue["phrase"] = spoken_money(cue["phrase"])
    rule = story.get("instructional", {})
    if "spoken_answer_phrases" in rule:
        rule["spoken_answer_phrases"] = [
            spoken_money(phrase) for phrase in rule["spoken_answer_phrases"]
        ]
    return story
