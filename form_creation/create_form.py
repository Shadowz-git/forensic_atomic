import csv
import json
import argparse
import random
from pathlib import Path
from typing import List, Dict

from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery

SCOPES = ['https://www.googleapis.com/auth/forms', 'https://www.googleapis.com/auth/drive']
GUIDA_ENG = "https://docs.google.com/document/d/1ns9brAp9qDCGmvQxRj3saY8RYmb9D_wcsr5CDwRt93s/edit?usp=sharing"
GUIDA_IT = "https://docs.google.com/document/d/1tSdNUjgopJgNsjzOh5jSaStdj_yCke1hJpxdpvC7fxA/edit?usp=sharing"

TRANSLATION_CACHE = {}

RELATION_DESCRIPTIONS = {
    'xIntent': 'What is PersonX trying to achieve or accomplish with this behavior? (i.e., their goal or the reason for their action)',
    'xNeed': 'What must PersonX already have, know, or be able to do BEFORE they can perform this action? (i.e., what are the necessary conditions or skills needed?)',
    'xAttr': 'What kind of person is PersonX? What character traits or qualities does this action reveal? (e.g., reckless, cunning, desperate, violent)',
    'xReact': 'How does PersonX feel or think about what happened as a result of their action? (i.e., their emotional or mental response)',
    'xWant': 'What does PersonX likely want to do next after this action? (i.e., what would they pursue or attempt to do?)',
    'xEffect': 'What exactly happens to Person X as a result of this action? (In other words, what are the consequences they face?)',
    'oReact': 'How would other people feel or what would they think if they knew about this? (i.e., others\' emotional or mental response)',
    'oWant': 'What would other people want to do or achieve in response to this action? (i.e., how might they react or what might they pursue?)',
    'oEffect': 'What are the direct consequences of this action for other people? (i.e., the consequences they experience)',
    'isAfter': 'What event or action must have happened BEFORE this one could occur? (i.e., what is the prerequisite event or cause?)',
    'HasSubEvent': 'What are the smaller actions or steps that make up this main event? (i.e., what needs to happen to accomplish this action?)',
    'Causes': 'What is the outcome, result, or consequence of this action? (i.e., what happens directly because of this event?)'
}

UI_MAP = {
    'Score (0-100)': 'Logical Coherence Index (Scale 0-100)',
    'Vote': 'Final Validation Decision',
    'Approve': 'APPROVE (All the criteria met)',
    'Reject': 'REJECT',
    'Reason (Optional, max 30 words)': 'Brief Explanation for your Decision (Optional - 30 words max)',
    'Enter a score between 0 and 100': (
        "SCALING GUIDE:\n"
        "- 100: PERFECT (The event meets all four criteria).\n"
        "- 50: POSSIBLE (The details might be true, even if they aren't the only possibility).\n"
        "- 0: IMPOSSIBLE (The event presented makes absolutely no sense, lacks “common sense,” is illogical, and does not meet any of the four criteria)."
    ),
}

def translate_text(text: str) -> str:
    if not text or not str(text).strip():
        return text
    if text in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[text]
    try:
        from argostranslate import translate
        translated = translate.translate(text, 'en', 'it')
        TRANSLATION_CACHE[text] = translated
        return translated
    except Exception:
        return text


def init_translation():
    try:
        # Fixed import for package_manager
        import argostranslate.package_manager
        pm = argostranslate.package_manager
        pm.update_package_index()
        available = pm.get_available_packages()
        package = next(p for p in available if p.from_code == 'en' and p.to_code == 'it')
        pm.install_packages([package])
    except Exception as e:
        print(f"Translation init skipped: {e}")


class FormCreator:
    def __init__(self, creds_file: str, translate: bool):
        self.translate = translate
        self.current_index = 0
        self._requests = []
        path = Path(creds_file)
        if not path.exists():
            raise FileNotFoundError(f"Missing: {creds_file}")
        flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
        self.creds = flow.run_local_server(port=0)
        self.service = googleapiclient.discovery.build('forms', 'v1', credentials=self.creds)

    def create_form(self, title: str, description: str):
        body = {'info': {'title': title}}
        form = self.service.forms().create(body=body).execute()
        fid = form['formId']
        if description:
            req = {
                'requests': [{'updateFormInfo': {'info': {'description': description}, 'updateMask': 'description'}}]}
            self.service.forms().batchUpdate(formId=fid, body=req).execute()
        return fid

    def _get_label(self, key: str) -> str:
        return f"{UI_MAP.get(key, key)}"

    def queue(self, item: Dict):
        self._requests.append({'createItem': {'item': item, 'location': {'index': self.current_index}}})
        self.current_index += 1

    def flush(self, fid: str):
        if not self._requests: return
        self.service.forms().batchUpdate(formId=fid, body={'requests': self._requests}).execute()
        self._requests = []

    def add_event_item(self, idx: int, data: Dict, rels: List[str]):
        en_anno = ""
        it_anno = ""
        for r in rels:
            definition = RELATION_DESCRIPTIONS.get(r, "")
            val = data.get(r, '[]')
            en_anno += f"{r} - {definition}:\nValue: {val}\n\n"
            if self.translate:
                it_anno += f"- {r}: {translate_text(str(val))}\n"

        if self.translate:
            desc = (
                f"ITA: Evento: {translate_text(data.get('event'))}\n"
                f"Contesto: {translate_text(data.get('brief_context'))}\n"
                f"Categoria: {translate_text(data.get('crime_category'))}\n"
                f"ANNOTAZIONI:\n{it_anno}\n"
                f"--------------------------------------------------\n"
                f"ENG: Event: {data.get('event')}\n"
                f"Context: {data.get('brief_context')}\n"
                f"Category: {data.get('crime_category')}\n"
                f"ANNOTATIONS:\n{en_anno}"
            )
        else:
            desc = (
                    f"Quick Guide (English): {GUIDA_ENG}\n"
                    f"Mini Guida (Italiano): {GUIDA_IT}\n\n"
                    
                    f"Event: {data.get('event')}\n\n"
                    f"Context: {data.get('brief_context')}\n\n"
                    f"Category: {data.get('crime_category')}\n\n"
                    f"ANNOTATIONS:\n{en_anno}")

        self.queue({'title': f"Event #{idx}", 'description': desc, 'textItem': {}})

    def add_questions(self):
        # Score field (Regex not supported via API v1)
        self.queue({
            'title': self._get_label('Score (0-100)'),
            'description': UI_MAP['Enter a score between 0 and 100'],
            'questionItem': {
                'question': {
                    'required': True,
                    'textQuestion': {}
                }
            }
        })
        # Vote field
        self.queue({
            'title': self._get_label('Vote'),
            'questionItem': {
                'question': {
                    'required': True,
                    'choiceQuestion': {
                        'type': 'RADIO',
                        'options': [
                            {'value': self._get_label('Approve')},
                            {'value': self._get_label('Reject')}
                        ]
                    }
                }
            }
        })
        # Optional Reason field
        self.queue({
            'title': self._get_label('Reason (Optional, max 30 words)'),
            'questionItem': {
                'question': {
                    'required': False,
                    'textQuestion': {'paragraph': True}
                }
            }
        })


def save_metadata(fid: str, edit_url: str, share_url: str, events: List[Dict], seed: int):
    # Save sampled events
    with open(f"sampled_events_seed_{seed}.json", 'w', encoding='utf-8') as f:
        json.dump({'seed': seed, 'events': events}, f, indent=2, ensure_ascii=False)
    # Save form metadata
    with open(f"form_metadata_{fid}.json", 'w', encoding='utf-8') as f:
        json.dump({'fid': fid, 'edit': edit_url, 'share': share_url, 'count': len(events)}, f, indent=2)


def load_data(path: str, sample: bool, size: int, seed: int):
    with open(path, encoding='utf-8') as f:
        data = list(csv.DictReader(f))
    if sample and len(data) > size:
        if seed is not None: random.seed(seed)
        data = random.sample(data, size)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    parser.add_argument('--title', default='Forensic Validation')
    parser.add_argument('--credentials', default='client_secrets.json')
    parser.add_argument('--random-sample', action='store_true')
    parser.add_argument('--sample-size', type=int, default=50)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--italian', action='store_true')
    parser.add_argument('--batch-size', type=int, default=20)
    args = parser.parse_args()

    if args.italian: init_translation()

    events = load_data(args.csv, args.random_sample, args.sample_size, args.seed)
    creator = FormCreator(args.credentials, args.italian)

    instr = (
        "This survey asks you to evaluate short descriptions of criminal or forensic situations."
        "For each case, you will see an event, its category, and additional details such as intentions, traits, and consequences."
        "Your task is to judge whether these elements make sense together and reflect common human reasoning."
        "You should consider clarity, logical consistency, whether the crime category can be inferred from the context, "
        "and whether the outcomes are proportionate to the action."
        "Finally, assign a score from 0 to 100 and indicate whether the event should be approved or rejected. You may also add an optional comment if needed."
        "Please read this guide to understand what it is about and how to complete the survey.\n"
        f"Quick Guide (English): {GUIDA_ENG}\n"
        f"Per favore, leggi questa guida per capire di cosa parla e come compilare il sondaggio.\n"
        f"Mini Guida (Italiano): {GUIDA_IT}"
        ""
    )
    fid = creator.create_form(args.title, instr)
    rels = ['xIntent', 'xAttr', 'xEffect', 'oEffect']

    for i, ev in enumerate(events, 1):
        creator.add_event_item(i, ev, rels)
        creator.add_questions()
        if i < len(events): creator.queue({'pageBreakItem': {}})
        if i % args.batch_size == 0 or i == len(events):
            creator.flush(fid)
            print(f"Batch processed: {i}/{len(events)}")

    edit_url = f"https://docs.google.com/forms/d/{fid}/edit"
    share_url = f"https://docs.google.com/forms/d/{fid}/viewform"
    save_metadata(fid, edit_url, share_url, events, args.seed)

    print(f"\nEdit: {edit_url}\nShare: {share_url}")


if __name__ == '__main__':
    main()