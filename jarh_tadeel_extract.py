import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


# =========================
# DATA MODEL
# =========================
@dataclass
class JarhTadilRecord:
    narrator_id: str
    full_name: str
    taadil: List[Dict]
    jarh: List[Dict]
    unclassified: List[Dict]
    teachers: List[str]
    students: List[str]
    source: Dict[str, any]


# =========================
# EXTRACTOR
# =========================
class JarhWaTadilExtractor:

    def __init__(self):
        self.records = []
        self.counter = 1

        # ---- Taʿdīl (Approval)
        self.taadil_terms = {
            'ثقة ثقة': 'Thiqa Thiqa',
            'ثقة ثبت': 'Thiqa Thabt',
            'ثقة حافظ': 'Thiqa Hafiz',
            'إمام حافظ': 'Imam Hafiz',
            'حجة': 'Hujjah',
            'ثقة': 'Thiqa',
            'ثبت': 'Thabt',
            'صدوق': 'Saduq',
            'لا بأس به': 'La ba\'s bihi',
            'محله الصدق': 'Truthful',
            'صالح الحديث': 'Salih al-Hadith',
            'يكتب حديثه': 'His hadith is written',
            'صدوق يهم': 'Saduq (but makes mistakes)',
            'صالح': 'Salih',
            'شيخ': 'Shaykh',
            'وسط': 'Average',
            "صالح الحديث": "Salih al-hadith"
        }

        # ---- Jarḥ (Criticism)
        self.jarh_terms = {
            'وسط': 'Average',
            'ضعيف': 'Da\'if',
            'لين الحديث': 'Layyin al-Hadith',
            'ليس بالقوي': 'Not strong',
            'يهم': 'Makes mistakes',
            'منكر الحديث': 'Munkar al-Hadith',
            'سيئ الحفظ': 'Poor memory',
            'متروك': 'Matruk',
            'متروك الحديث': 'Matruk al-Hadith',
            'كذاب': 'Kadhdhab',
            'وضاع': 'Fabricator',
            'ساقط': 'Saqit',
            "ضعيف": "Daif",
            "ليس بالقوي": "Not strong",
            "فيه لين": "Layyin"
        }

    # =========================
    # UTILITIES
    # =========================
    def arabic_to_western(self, text: str) -> str:
        return text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

    def remove_footnotes(self, text: str) -> str:
        text = re.sub(r'\(\s*[٠-٩0-9]+\s*\)', '', text)
        text = re.sub(r'\[\s*[^]]+?\s*\]', '', text)
        return text

    # =========================
    # SEGMENT BIOGRAPHIES
    # =========================
    def segment_entries(self, text: str) -> List[str]:
        text = self.arabic_to_western(text)
        parts = re.split(r'(?=\n?\d+\s*-\s*)', text)
        return [p.strip() for p in parts if re.match(r'^\d+\s*-\s*', p)]

    # =========================
    # NAME EXTRACTION
    # =========================
    def extract_name(self, entry: str) -> Optional[str]:
        header = self.remove_footnotes(entry.split('\n', 1)[0])
        m = re.match(
            r'^\d+\s*-\s*([أ-ي]+(?:\s+(?:بن|ابن)\s+[أ-ي]+){1,6})',
            header
        )
        return m.group(1).strip() if m else None

    # =========================
    # TEACHERS & STUDENTS
    # =========================
    def extract_teachers_students(self, text: str):
        teachers, students = set(), set()

        teacher_patterns = [
        r'روى عن\s+([أ-ي\sو,]+(?:بن\s+[أ-ي]+)+)',
        r'سمع(?:\s+من)?\s+([أ-ي\sو,]+(?:بن\s+[أ-ي]+)+)'
        ]

        student_patterns = [
        r'روى عنه\s+([أ-ي\sو,]+(?:بن\s+[أ-ي]+)+)',
        r'حدث عنه\s+([أ-ي\sو,]+(?:بن\s+[أ-ي]+)+)'
        ]

        def split_names(raw: str):
        # Split by و or comma, remove extra spaces
            names = re.split(r'[و,]+', raw)
            return [n.strip() for n in names if n.strip()]

        for p in teacher_patterns:
            for m in re.finditer(p, text):
                for name in split_names(m.group(1)):
                    teachers.add(name)

        for p in student_patterns:
            for m in re.finditer(p, text):
                for name in split_names(m.group(1)):
                    students.add(name)

        return list(teachers), list(students)

    # =========================
    # JARḤ–TAʿDĪL EXTRACTION
    # =========================
    def extract_judgements(self, text: str):
        taadil, jarh, unclassified = [], [], []

        evaluator_pattern = r'(?:قال|وقال)\s+([أ-ي\s]+?)[:：]\s*([^\.،\n]{2,200})'

        for m in re.finditer(evaluator_pattern, text):
            evaluator = m.group(1).strip()
            phrase = m.group(2).strip()

            classified = False

            for ar, en in self.taadil_terms.items():
                if ar in phrase:
                    taadil.append({
                        "statement": en,
                        "exact_text": phrase,
                        "evaluated_by": evaluator
                    })
                    classified = True

            for ar, en in self.jarh_terms.items():
                if ar in phrase:
                    jarh.append({
                        "statement": en,
                        "exact_text": phrase,
                        "evaluated_by": evaluator
                    })
                    classified = True

            if not classified:
                unclassified.append({
                    "exact_text": phrase,
                    "evaluated_by": evaluator
                })

        # ---- Standalone judgements
        for ar, en in self.taadil_terms.items():
            if ar in text:
                taadil.append({
                    "statement": en,
                    "exact_text": ar,
                    "evaluated_by": None
                })

        for ar, en in self.jarh_terms.items():
            if ar in text:
                jarh.append({
                    "statement": en,
                    "exact_text": ar,
                    "evaluated_by": None
                })

        return taadil, jarh, unclassified

    # =========================
    # PROCESS ENTRY
    # =========================
    def process_entry(self, entry: str, page: int, vol: int):
        name = self.extract_name(entry)
        if not name:
            return None

        taadil, jarh, unclassified = self.extract_judgements(entry)
        teachers, students = self.extract_teachers_students(entry)

        record = JarhTadilRecord(
            narrator_id=f"N{self.counter:05d}",
            full_name=name,
            taadil=taadil,
            jarh=jarh,
            unclassified=unclassified,
            teachers=teachers,
            students=students,
            source={"volume": vol, "page": page}
        )

        self.counter += 1
        return record

    # =========================
    # JSON DRIVER 
    # =========================
    def extract_from_json(self, pages: List[Dict], start_volume=2):
        for page in pages:
            vol = int(self.arabic_to_western(str(page.get("vol", "1"))))

            if vol < start_volume:
                continue

            entries = self.segment_entries(page.get("text", ""))

            for entry in entries:
                record = self.process_entry(entry, page.get("page"), vol)
                if record:
                    self.records.append(asdict(record))

        return self.records

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)


# =========================
# MAIN
# =========================
def main():
    INPUT = "all_pages_complete.json"
    OUTPUT = "narrator_jarh_tadil.json"

    extractor = JarhWaTadilExtractor()

    with open(INPUT, encoding="utf-8") as f:
        pages = json.load(f)

    extractor.extract_from_json(pages, start_volume=2)
    extractor.save(OUTPUT)

    print(f"✓ Extracted {len(extractor.records)} narrators (Jarḥ–Taʿdīl)")


if __name__ == "__main__":
    main()
