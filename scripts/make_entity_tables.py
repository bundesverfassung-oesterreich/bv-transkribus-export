import pandas as pd

df = pd.read_csv("../metadata.csv")
wer_an_wen = set(df["weranwen"].values)


data = []
persons = set()
split_token = " an "
for x in wer_an_wen:
    sender = ""
    receiver = ""
    try:
        if split_token in x:
            sender, receiver = x.split(split_token)
    except TypeError:
        continue
    if sender.endswith(","):
        sender = sender[:-1]
    persons.add(sender.strip())
    persons.add(receiver.strip())

data = []
for i, x in enumerate(sorted(persons)):
    item = {"name": x, "gnd": "", "emt_id": f"emt_person_{i+1}"}
    data.append(item)

person_df = pd.DataFrame(data)
person_df.to_csv("../persons.csv", index=False)
orte = [x for x in set(df["Ort"].values) if isinstance(x, str)]
data = []
for i, x in enumerate(sorted(orte)):
    item = {"name": x, "geonames": "", "emt_id": f"emt_place_{i+1}"}
    data.append(item)
places = pd.DataFrame(data)
places.to_csv("../places.csv", index=False)
