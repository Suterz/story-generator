"""Find inspectable passages in a frozen packet and check the cited population."""
import hashlib
import re


def keywords(text):
    return set(re.findall(r"[a-z0-9.]+(?:-[a-z0-9.]+)?", text.casefold()))


def retrieve(packet, query):
    sought = keywords(query)
    return sorted(packet["passages"], key=lambda row: (
        -len(sought & keywords(row["paragraph"])), row["id"]))


def evidence_for(packet):
    results = retrieve(packet, packet["query"])
    ids = {row["id"]: row for row in results}
    if len(ids) != len(results) or len(ids) != 2:
        raise ValueError("citation comparison needs two distinct retrieved paragraphs")
    evidence = {}
    for row in results:
        quote = " ".join(row["visible_lines"])
        start = row["paragraph"].find(quote)
        if start < 0:
            raise ValueError(f"{row['id']}: on-screen excerpt is not in the frozen paragraph")
        evidence[row["id"]] = {
            "population": row["population"], "supports": row["population"] == packet["population"],
            "quote_characters": [start, start + len(quote)],
            "paragraph_sha256": hashlib.sha256(row["paragraph"].encode()).hexdigest(),
        }
    if evidence["support"]["supports"] is not True or evidence["mismatch"]["supports"] is not False:
        raise ValueError("citation controls must distinguish the approved population from the counterexample")
    return {"url": packet["url"], "locator": packet["locator"], "question": packet["query"],
            "ranked_passages": [row["id"] for row in results], "inspected": evidence}
