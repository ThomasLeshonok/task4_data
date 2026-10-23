import re
import pandas as pd

TITLE_RX = re.compile(
    r"^(?:(?:the\s+hon|mr|mrs|ms|miss|dr|prof|rev|fr|msgr|sen|rep|gov|pres|amb|hon|sir|dame)\b\.?\s+)+", re.I
)
SUFFIX_RX = re.compile(
    r"(?:[\s,]+(?:jr|sr|ii|iii|iv|v|i|phd|md|dds|dvm|do|dc|jd|cpa|esq|lld|vm|ret)\.?)+$", re.I
)

def strip_titles(names: pd.Series) -> pd.Series:
    return (
        names.str.strip()
        .str.replace(TITLE_RX, "", regex=True)
        .str.replace(SUFFIX_RX, "", regex=True)
        .str.strip()
    )
