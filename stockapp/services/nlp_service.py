import spacy

nlp = spacy.load("en_core_web_sm")


def extract_stock_info(query: str) -> tuple[str | None, str | None, str]:
    doc = nlp(query)
    stock_name = None
    price_threshold = None
    comparison_type = "greater_than_equal"

    for ent in doc.ents:
        if ent.label_ in ["MONEY", "CARDINAL"]:
            price_threshold = ent.text
        elif ent.label_ in ["ORG", "GPE"]:
            stock_name = ent.text

    for token in doc:
        if "exceed" in token.lemma_ or "greater" in token.text or "above" in token.text:
            comparison_type = "greater_than_equal"
        elif "less" in token.text or "below" in token.text:
            comparison_type = "less_than_equal"

    return stock_name, price_threshold, comparison_type
