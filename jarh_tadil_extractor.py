import json
import re
from typing import List, Dict, Any, Set

class NarratorExtractor:
    def __init__(self):
        # Keywords for taadil (approval/praise) 
        self.taadil_keywords = [
            'ثقة', 'صدوق', 'حافظ', 'متقن', 'ضابط', 'عدل', 'مأمون',
            'لا بأس به', 'صالح الحديث', 'يكتب حديثه', 'حجة', 'إمام',
            'ثبت', 'عابد', 'فاضل', 'صالح', 'مقبول', 'رجل صالح',
            'لا بأس', 'ما بال به', 'محله الصدق', 'صدق'
        ]
        
        # Keywords for jarh (criticism) 
        self.jarh_keywords = [
            'ضعيف', 'متروك', 'كذاب', 'وضاع', 'منكر الحديث', 'واه',
            'ليس بشيء', 'لا يحتج به', 'مجهول', 'ضعفه', 'تركه',
            'ليس بالقوي', 'فيه ضعف', 'منكر', 'لا يعرف', 'مجروح',
            'ليس بثقة', 'ضعيف الحديث'
        ]
        
        # Arabic to English numeral mapping
        self.arabic_to_english = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    
    def convert_arabic_numerals(self, text: str) -> str:
        """Convert Arabic-Indic numerals to English numerals"""
        return text.translate(self.arabic_to_english)
    
    def extract_narrators(self, json_file_path: str) -> List[Dict[str, Any]]:
        """Extract narrator information from JSON file"""
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        narrators = []
        
        # Handle the nested array structure
        for volume_pages in data:
            if isinstance(volume_pages, list):
                for entry in volume_pages:
                    if isinstance(entry, dict):
                        text = entry.get('text', '')
                        volume = entry.get('vol', '')
                        page = entry.get('page', '')
                        
                        narrator_entries = self._extract_narrator_entries(text, volume, page)
                        narrators.extend(narrator_entries)
            elif isinstance(volume_pages, dict):
                text = volume_pages.get('text', '')
                volume = volume_pages.get('vol', '')
                page = volume_pages.get('page', '')
                
                narrator_entries = self._extract_narrator_entries(text, volume, page)
                narrators.extend(narrator_entries)
        
        return narrators
    
    def _extract_narrator_entries(self, text: str, volume: str, page: str) -> List[Dict[str, Any]]:
        """Extract individual narrator entries from text"""
        narrators = []
        
        # Convert Arabic numerals to English for processing
        text_converted = self.convert_arabic_numerals(text)
        
        # Pattern to match narrator entries
        pattern = r'(\d+)\s*-\s*([^\n]+)'
        
        matches = list(re.finditer(pattern, text_converted))
        
        for i, match in enumerate(matches):
            narrator_id = match.group(1)
            
            # Get full text block for this narrator
            start_pos = match.start()
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(text_converted)
            
            full_text = text_converted[start_pos:end_pos]
            full_text_original = text[start_pos:end_pos]
            
            # Extract narrator name
            name = self._extract_name(full_text)
            
            # Extract taadil and jarh keywords only
            taadil = self._extract_keywords(full_text_original, self.taadil_keywords)
            jarh = self._extract_keywords(full_text_original, self.jarh_keywords)
            
            # Extract teachers (روى عن / سمع من)
            teachers = self._extract_teachers(full_text_original)
            
            # Extract students (روى عنه)
            students = self._extract_students(full_text_original)
            
            narrator_data = {
                "narrator_id": f"N{narrator_id.zfill(5)}",
                "full_name": name.strip(),
                "taadil": taadil,
                "jarh": jarh,
                "teachers": teachers,
                "students": students,
                "source": {
                    "volume": int(volume) if volume else 0,
                    "page": int(page) if page else 0
                }
            }
            
            narrators.append(narrator_data)
        
        return narrators
    
    def _extract_name(self, text: str) -> str:
        """Extract narrator name from text"""
        # Remove the number prefix
        text = re.sub(r'^\d+\s*-\s*', '', text)
        
        # Remove square brackets and their contents
        text = re.sub(r'\[.*?\]', '', text)
        
        # Remove footnote markers
        text = re.sub(r'\([٠-٩0-9]+\)', '', text)
        
        # Stop patterns for name extraction
        stop_patterns = [
            r'\sروت\s+عن',
            r'\sروى\s+عن',
            r'\sيروى\s+عن',
            r'\sحدث',
            r'\sقال',
            r'\sسمعت',
            r'\sنا\s',
            r'\sاسمها\s',
            r'\sاسمه\s',
            r'\sمن\s+اصحاب',
            r'\sله\s+صحبة',
            r'\sمدينى',
            r'\sبكري',
            r'\sخزاعية',
            r'\sانصارية',
            r'\sامرأة'
        ]
        
        min_pos = len(text)
        for pattern in stop_patterns:
            match = re.search(pattern, text)
            if match and match.start() < min_pos:
                min_pos = match.start()
        
        if min_pos < len(text):
            name = text[:min_pos].strip()
        else:
            words = text.split()[:5]
            name = ' '.join(words)
        
        name = name.strip().rstrip(',،;؛:.')
        
        # Limit to 6 words
        words = name.split()
        if len(words) > 6:
            name = ' '.join(words[:6])
        
        return name
    
    def _extract_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Extract only the taadil or jarh keywords found in text"""
        found_keywords = []
        
        for keyword in keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(found_keywords))
    
    def _extract_teachers(self, text: str) -> List[str]:
        """Extract teachers (those the narrator learned from)"""
        teachers = []
        
        # Patterns for "narrated from" or "heard from"
        patterns = [
            r'روى\s+عن\s+([^،\.]+?)(?=[،\.\n]|روى عنه|سمعت|قال|نا\s|و)',
            r'روت\s+عن\s+([^،\.]+?)(?=[،\.\n]|روى عنه|سمعت|قال|نا\s|و)',
            r'سمع\s+من\s+([^،\.]+?)(?=[،\.\n]|روى عنه|سمعت|قال|نا\s|و)',
            r'سمعت\s+من\s+([^،\.]+?)(?=[،\.\n]|روى عنه|سمعت|قال|نا\s|و)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Split by 'و' to get individual names
                names = re.split(r'\s+و\s+', match)
                
                for name in names:
                    teacher = name.strip()
                    # Clean up
                    teacher = re.sub(r'\[.*?\]', '', teacher)
                    teacher = re.sub(r'\([٠-٩0-9]+\)', '', teacher)
                    teacher = teacher.strip()
                    
                    # Remove common words that aren't names
                    if teacher.startswith('عن '):
                        teacher = teacher[3:].strip()
                    
                    # Skip if too short or contains metadata
                    if (len(teacher) > 2 and 
                        'بياض' not in teacher and 
                        'احاديث' not in teacher and
                        'حديث' not in teacher and
                        teacher not in teachers):
                        teachers.append(teacher)
        
        return teachers
    
    def _extract_students(self, text: str) -> List[str]:
        """Extract students (those who narrated from this narrator)"""
        students = []
        
        # Patterns for "narrated from him/her"
        patterns = [
            r'روى\s+عنه[اء]?\s+([^،\.]+?)(?=[،\.\n]|روى عن|سمعت|قال|نا\s|و)',
            r'روت\s+عنه[اء]?\s+([^،\.]+?)(?=[،\.\n]|روى عن|سمعت|قال|نا\s|و)',
            r'حدث\s+عنه[اء]?\s+([^،\.]+?)(?=[،\.\n]|روى عن|سمعت|قال|نا\s|و)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Split by 'و' to get individual names
                names = re.split(r'\s+و\s+', match)
                
                for name in names:
                    student = name.strip()
                    # Clean up
                    student = re.sub(r'\[.*?\]', '', student)
                    student = re.sub(r'\([٠-٩0-9]+\)', '', student)
                    student = student.strip()
                    
                    # Remove common prefixes
                    if student.startswith('عنه '):
                        student = student[4:].strip()
                    if student.startswith('عنها '):
                        student = student[5:].strip()
                    
                    # Skip if too short or contains metadata
                    if (len(student) > 2 and 
                        'بياض' not in student and 
                        'احاديث' not in student and
                        'حديث' not in student and
                        student not in students):
                        students.append(student)
        
        return students
    
    def save_to_json(self, narrators: List[Dict[str, Any]], output_file: str):
        """Save extracted narrators to JSON file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(narrators, f, ensure_ascii=False, indent=2)
        print(f"✓ Extracted {len(narrators)} narrators to {output_file}")


def main():
    """Main execution function"""
    extractor = NarratorExtractor()
    
    input_file = 'all_pages_complete.json'
    output_file = 'narrator_jarh_tadil.json'
    
    try:
        print(f"Reading from {input_file}...")
        narrators = extractor.extract_narrators(input_file)
        
        extractor.save_to_json(narrators, output_file)
        
        print(f"\n=== Extraction Summary ===")
        print(f"Total narrators: {len(narrators)}")
        
        taadil_count = sum(1 for n in narrators if n['taadil'])
        jarh_count = sum(1 for n in narrators if n['jarh'])
        teachers_count = sum(1 for n in narrators if n['teachers'])
        students_count = sum(1 for n in narrators if n['students'])
        
        print(f"Narrators with taadil: {taadil_count}")
        print(f"Narrators with jarh: {jarh_count}")
        print(f"Narrators with teachers: {teachers_count}")
        print(f"Narrators with students: {students_count}")
        
        print(f"\n=== Sample Results ===")
        for narrator in narrators[:5]:
            print(f"\n{'='*60}")
            print(f"ID: {narrator['narrator_id']}")
            print(f"Name: {narrator['full_name']}")
            print(f"Source: Vol {narrator['source']['volume']}, Page {narrator['source']['page']}")
            
            if narrator['taadil']:
                print(f"Taadil: {', '.join(narrator['taadil'])}")
            
            if narrator['jarh']:
                print(f"Jarh: {', '.join(narrator['jarh'])}")
            
            if narrator['teachers']:
                print(f"Teachers ({len(narrator['teachers'])}): {narrator['teachers'][:3]}")
            
            if narrator['students']:
                print(f"Students ({len(narrator['students'])}): {narrator['students'][:3]}")
        
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found!")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file - {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()