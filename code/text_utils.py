from indic_transliteration import sanscript
from indic_transliteration.sanscript import SchemeMap, SCHEMES, transliterate
from skrutable.meter_identification import MeterIdentifier
from dot_dict import DotDict

meter_identifier = MeterIdentifier()


def iast2dev(line):
    return transliterate(line, sanscript.IAST, sanscript.DEVANAGARI)


def get_chhanda(verse):
    out = DotDict()
    try:
        meter = meter_identifier.identify_meter(verse, from_scheme="DEV")
    except Exception:
        return None
    label = ""
    pre_label = iast2dev(meter.meter_label.split(" ")[0].strip())
    if pre_label in ["न", "अज्ञातसमवृत्त", "अज्ञातार्धसमवृत्त"]:
        return None
    if pre_label == "अनुष्टुभ्":
        label = "अनुष्टुप्"
    else:
        label = pre_label
        pass

    out["n"] = label
    return out
