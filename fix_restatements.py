#!/usr/bin/env python3
"""يعيد كتابة أقسام إعادة الصياغة في data/exams_generated.json.

النسخة الأولى كان متوسط طول خيارها ٨.٨ كلمة مقابل ١٤.٧ في الكتاب، أي أسهل
بوضوح: الخيار القصير يُستبعد أسرع. هذه النسخة تطابق طول الكتاب وكثافته.
"""

import json
import sys
from pathlib import Path

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# (معرّف الامتحان، فهرس القسم): [(الجملة، [الخيارات الأربعة]، فهرس الصحيح), ...]
NEW = {
 ("g1", 3): [
  ("Not until the results had been independently replicated did the journal agree to publish the paper.",
   ["The journal published the paper first and only later asked for the results to be replicated.",
    "The journal agreed to publish the paper only after other researchers had reproduced the results.",
    "The journal rejected the paper even though independent researchers had successfully reproduced its results.",
    "The results were replicated precisely because the journal had already agreed to publish the paper."], 1),
  ("The city would almost certainly have flooded had the flood barrier not been raised in time.",
   ["Because the barrier was raised before the water rose, the city escaped the flooding.",
    "The barrier was raised far too late, and as a result much of the city flooded.",
    "No barrier was ever raised at all, which is why the city suffered such extensive flooding.",
    "The city will be flooded unless someone manages to raise the barrier within the next few hours."], 0),
  ("Far from discouraging her, the criticism she received made her work considerably harder than before.",
   ["The criticism upset her so much that she produced far less work than she had previously.",
    "She paid no attention whatsoever to the criticism and carried on working exactly as before.",
    "Rather than putting her off, the criticism led her to put in significantly more effort.",
    "She worked harder mainly in order to avoid being criticised by the same people again."], 2)],

 ("g1", 4): [
  ("The scheme has little chance of succeeding unless the money allocated to it is doubled.",
   ["The scheme will succeed comfortably even if no further money is allocated to it.",
    "Doubling the money allocated to the scheme would almost certainly cause it to fail.",
    "Unless twice as much money is provided, the scheme is unlikely to succeed.",
    "The money has already been doubled, so the scheme is now certain to succeed."], 2),
  ("Few of the candidates interviewed had any experience relevant to the position on offer.",
   ["Most of the candidates who were interviewed lacked experience relevant to the post.",
    "Every candidate interviewed brought a great deal of relevant experience to the position.",
    "The candidates had relevant experience but none of the qualifications the post required.",
    "Only a small number of people applied for the position that was on offer."], 0),
  ("He is said to have turned down the award on three separate occasions before finally accepting it.",
   ["According to reports, he refused the award three times and then accepted it at last.",
    "He accepted the award immediately on all three occasions on which it was offered.",
    "The committee refused to give him the award three times before eventually agreeing.",
    "He announced well in advance that he intended to refuse the award three times."], 0)],

 ("g2", 3): [
  ("Hardly anyone at the meeting raised any objection to the proposal that had been put forward.",
   ["Almost none of those present at the meeting objected to the proposal.",
    "Everyone at the meeting objected strongly to the proposal that was put forward.",
    "The proposal was withdrawn before anyone at the meeting had a chance to discuss it.",
    "Only the most difficult parts of the proposal attracted any criticism at the meeting."], 0),
  ("Only by planting large numbers of street trees can the city hope to reduce its summer temperatures.",
   ["Planting street trees is one of several methods the city could use to cool itself.",
    "Planting large numbers of street trees is the only way the city can lower summer temperatures.",
    "There is nothing at all the city can do to reduce its temperatures in summer.",
    "Street trees have been shown to raise rather than lower temperatures during the summer."], 1),
  ("The scheme had to be postponed indefinitely owing to a severe shortage of public funds.",
   ["The scheme was abandoned altogether because it had been very badly designed from the start.",
    "A serious lack of public money forced the scheme to be delayed with no new date set.",
    "The scheme went ahead exactly as planned in spite of the shortage of public funds.",
    "The shortage of public funds was itself caused by the enormous cost of the scheme."], 1)],

 ("g2", 4): [
  ("She would sooner resign from her post than compromise the principles she has always held.",
   ["She resigned from her post shortly after abandoning the principles she once held.",
    "She would rather give up her position than act against her long-held principles.",
    "She compromised her principles in order to hold on to the post she valued.",
    "She was forced out of her post because of the principles she insisted on keeping."], 1),
  ("It was not until 1980 that the practice was finally outlawed throughout the country.",
   ["The practice remained perfectly legal everywhere in the country until 1980.",
    "The practice had already been banned across the country long before 1980 arrived.",
    "Despite repeated attempts, the practice has never actually been made illegal anywhere.",
    "The practice was made legal throughout the country for the first time in 1980."], 0),
  ("No matter how carefully the data had been collected, the conclusion drawn from them was flawed.",
   ["The data were gathered carelessly, which is precisely why the conclusion turned out wrong.",
    "The conclusion was perfectly sound because such great care had been taken over the data.",
    "The conclusion was mistaken despite all the care that went into collecting the data.",
    "Collecting data carefully is simply not possible in this particular field of research."], 2)],

 ("g3", 3): [
  ("So dark is the deep ocean that the majority of its inhabitants generate light of their own.",
   ["The deep ocean is so dark that most creatures living there produce their own light.",
    "Most deep-sea creatures deliberately avoid light because the ocean around them is dark.",
    "The ocean is dark precisely because its inhabitants absorb all the light reaching them.",
    "Very few of the animals living in the dark ocean produce any light at all."], 0),
  ("Had the funding not been cut halfway through, the survey would have covered all six sites.",
   ["Because the funding was cut, fewer than six sites were eventually surveyed.",
    "All six sites were surveyed despite the cut that was made to the funding.",
    "The funding was increased halfway through, which allowed all six sites to be surveyed.",
    "The survey was called off completely as soon as the funding was reduced."], 0),
  ("Scarcely had the submersible reached the seabed when its main camera stopped working.",
   ["The camera had already failed long before the submersible began its descent.",
    "The main camera failed almost immediately after the submersible arrived at the seabed.",
    "The submersible never reached the seabed at all because its main camera had failed.",
    "The camera continued working perfectly throughout the whole of the dive to the seabed."], 1)],

 ("g3", 4): [
  ("The species is by no means as rare as biologists once believed it to be.",
   ["The species has turned out to be far rarer than biologists had ever suspected.",
    "The species is considerably less rare than biologists used to think it was.",
    "No biologist has ever seriously believed this particular species to be a rare one.",
    "The species has become rare only within the last few decades of study."], 1),
  ("Rather than publishing the findings immediately, the team waited until they had been independently confirmed.",
   ["The team published straight away and only sought independent confirmation afterwards.",
    "The team decided in the end never to publish any of the findings at all.",
    "The team held the findings back until other researchers had confirmed them.",
    "The team confirmed the findings themselves but then refused to publish them."], 2),
  ("The glow serves both to attract unsuspecting prey and to deter approaching predators.",
   ["The glow draws prey in but has no effect whatsoever on approaching predators.",
    "The glow has two purposes: luring prey closer and driving predators away.",
    "The glow attracts predators towards the animal and frightens its prey away.",
    "The glow is of use only as a defence against predators, not for hunting."], 1)],

 ("g4", 3): [
  ("Not only did the printing press drive prices down, it also widened the reading public considerably.",
   ["The press lowered prices without having any real effect on the number of readers.",
    "The press both reduced the price of books and greatly increased the number of readers.",
    "The press pushed prices up and consequently reduced the size of the reading public.",
    "The press widened the reading public but made books considerably more expensive than before."], 1),
  ("Very little of this cheap printed material has come down to us in any form.",
   ["Most of the cheap printed material from that period survives to this day.",
    "Hardly any of this cheap printed material has survived until the present day.",
    "This kind of cheap material was in fact never actually printed at all.",
    "The material was so expensive that it was carefully preserved by its owners."], 1),
  ("It was the sheer scale of circulation, rather than the content itself, that alarmed the authorities.",
   ["The authorities were disturbed by what the books said, not by how many circulated.",
    "The authorities were entirely untroubled by printing, whatever its scale or its content.",
    "What worried the authorities was how widely material spread, not what it actually said.",
    "Both the content and the scale of circulation left the authorities completely indifferent."], 2)],

 ("g4", 4): [
  ("Were it not for the sharp fall in prices, very few new readers would have appeared.",
   ["Prices fell sharply, and as a direct result a great many new readers appeared.",
    "Prices did not fall at all, and yet large numbers of new readers appeared.",
    "New readers had already appeared in large numbers well before prices began to fall.",
    "The sharp fall in prices actually discouraged new readers from buying any books."], 0),
  ("Printers moved to other cities rather than submit to the rules imposed by the guild.",
   ["Printers accepted the rules laid down by the guild and remained in the city.",
    "Printers left for other cities instead of accepting the rules the guild imposed.",
    "The guild forced the printers to leave the city against their own wishes.",
    "Printers negotiated an entirely new set of rules with the guild before staying."], 1),
  ("By no means every book printed in the early period dealt with religious subjects.",
   ["Every single book printed in the early period was religious in its subject matter.",
    "Religious books were never printed at all during the early period of printing.",
    "Not all of the books printed in the early period were about religion.",
    "Only books on religious subjects were considered worth the cost of printing."], 2)],

 ("g5", 3): [
  ("Hardly any merchant ever travelled the entire length of the route from one end to the other.",
   ["Almost no merchant covered the whole route from one end of it to the other.",
    "Every merchant travelled the full length of the route at least once in his life.",
    "Merchants travelled the route in one direction only and never made the return journey.",
    "The route was far too short to require more than a single merchant."], 0),
  ("It was not the goods themselves but the ideas travelling with them that had the greater effect.",
   ["The goods that were traded mattered a great deal more than any ideas did.",
    "Neither the goods nor the ideas had much lasting effect on the regions involved.",
    "The ideas carried along the routes proved more influential than the goods themselves.",
    "Ideas and goods turned out to have had exactly the same degree of influence."], 2),
  ("Once sea routes had proved cheaper, the overland trade was no longer able to compete.",
   ["The overland trade remained considerably cheaper than transporting the same goods by sea.",
    "As soon as shipping became the cheaper option, the overland trade lost its advantage.",
    "Sea routes were always far more expensive than the equivalent routes overland.",
    "Both routes cost much the same and continued side by side for many centuries."], 1)],

 ("g5", 4): [
  ("The towns were left with monuments they could no longer afford to maintain properly.",
   ["The towns pulled their monuments down in order to save money on their upkeep.",
    "The towns kept monuments that had become too expensive for them to look after.",
    "The towns put up entirely new monuments once the overland trade had come to an end.",
    "The monuments were maintained instead by merchants who came from other regions."], 1),
  ("Not a single map surviving from the period marks a road of the kind later described.",
   ["Several maps from the period show the road clearly and in considerable detail.",
    "No surviving map from that period shows any road of the kind described.",
    "Exactly one map from the period marks the road, though not very accurately.",
    "Maps were simply never drawn at all during the period in question."], 1),
  ("Some historians contend that the very routes which carried paper westwards also carried the plague.",
   ["All historians are agreed that the routes carried paper and nothing else besides.",
    "Certain historians argue that the routes transmitted disease as well as paper.",
    "Historians firmly deny that the routes ever carried anything harmful at all.",
    "Paper and plague are known to have travelled by entirely separate routes."], 1)],
}


def main():
    p = Path(__file__).parent / "data" / "exams_generated.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    n = 0
    for ex in d["exams"]:
        for si, sec in enumerate(ex["sections"]):
            key = (ex["id"], si)
            if key not in NEW:
                continue
            rows = NEW[key]
            assert sec["type"] == "restatement", key
            assert len(rows) == len(sec["questions"]), key
            sec["questions"] = [{"text": t, "options": o, "correct": c} for t, o, c in rows]
            n += len(rows)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    lens = [len(o.split()) for _, opts, _ in
            (r for rows in NEW.values() for r in rows) for o in opts]
    stems = [len(t.split()) for rows in NEW.values() for t, _, _ in rows]
    print("أُعيدت كتابة %d سؤال إعادة صياغة" % n)
    print("متوسط طول الخيار: %.1f كلمة (الكتاب ١٤.٧)" % (sum(lens) / len(lens)))
    print("متوسط طول الجملة: %.1f كلمة (الكتاب ١٤.١)" % (sum(stems) / len(stems)))


if __name__ == "__main__":
    main()
