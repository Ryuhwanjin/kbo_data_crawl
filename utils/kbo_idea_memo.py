import os
import json
import datetime
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMO_FILE = os.path.join(ROOT_DIR, "saber_data", "ideas.json")

def load_ideas():
    """아이디어 목록 JSON 로드 및 ideas.md 부재 시 자동 컴파일"""
    os.makedirs(os.path.dirname(MEMO_FILE), exist_ok=True)
    if not os.path.exists(MEMO_FILE):
        return []
    try:
        with open(MEMO_FILE, "r", encoding="utf-8") as f:
            ideas = json.load(f)
        # ideas.md가 없으면 자동 빌드 수행
        if not os.path.exists(os.path.join(ROOT_DIR, "ideas.md")):
            compile_to_markdown(ideas)
        return ideas
    except Exception:
        return []

def save_ideas(ideas):
    """아이디어 목록 JSON 저장 및 ideas.md 마크다운 컴파일"""
    try:
        with open(MEMO_FILE, "w", encoding="utf-8") as f:
            json.dump(ideas, f, indent=4, ensure_ascii=False)
        # 마크다운 자동 컴파일 기동
        compile_to_markdown(ideas)
    except Exception as e:
        print(f"❌ 아이디어 저장 중 오류 발생: {e}")

def compile_to_markdown(ideas):
    """아이디어 데이터를 로컬 ideas.md 표준 마크다운 문서로 자동 변환"""
    md_path = os.path.join(ROOT_DIR, "ideas.md")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 💡 KBO 콘텐츠 기획 아이디어 & TODO 리스트\n\n")
            f.write("이 문서는 디스코드 개인 채널 및 터미널 매니저를 통해 수집된 콘텐츠 기획 목록입니다.\n")
            f.write("AI 에이전트(Antigravity)와 Pair Programming 시 이 파일의 기획 번호를 지정하여 업무를 지시할 수 있습니다.\n\n")
            
            todo_list = [i for i in ideas if i.get("status") == "TODO"]
            done_list = [i for i in ideas if i.get("status") == "DONE"]
            
            f.write("## 🟢 대기 중인 기획 및 할 일 (TODO)\n")
            if todo_list:
                for item in todo_list:
                    f.write(f"- [ ] **ID {item['id']}**: {item['text']} *(등록: {item['date'][:16]})*\n")
            else:
                f.write("- [x] 모든 기획이 완료되었습니다! 새로운 아이디어를 등록해 보세요.\n")
            f.write("\n")
            
            f.write("## 🔴 완료된 기획 및 아카이브 (DONE)\n")
            if done_list:
                for item in done_list:
                    f.write(f"- [x] **ID {item['id']}**: {item['text']} *(완료됨)*\n")
            else:
                f.write("- 완료 항목이 아직 없습니다.\n")
                
        print(f"📝 [Compiler] 'ideas.md' 마크다운 문서 컴파일 성공!")
    except Exception as e:
        print(f"❌ 마크다운 컴파일 중 오류 발생: {e}")


def add_idea(text):
    """새 글감 아이디어 추가"""
    ideas = load_ideas()
    new_id = max([i.get("id", 0) for i in ideas] + [0]) + 1
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    idea = {
        "id": new_id,
        "date": now_str,
        "text": text,
        "status": "TODO"
    }
    ideas.append(idea)
    save_ideas(ideas)
    print(f"✨ [Memo Manager] 새 아이디어가 추가되었습니다: ID {new_id} -> '{text}'")

def list_ideas(show_all=False):
    """아이디어 목록 보기"""
    ideas = load_ideas()
    filtered = ideas if show_all else [i for i in ideas if i.get("status") == "TODO"]
    
    if not filtered:
        print("📭 저장된 미완료 아이디어가 없습니다. 새 아이디어를 추가해 보세요!")
        return
        
    print("\n==================================================================================")
    print(f"💡 [KBO 콘텐츠 기획 아이디어 목록] (총 {len(filtered)}개)")
    print("==================================================================================")
    print(f"{'ID':<4} | {'등록 일시':<19} | {'상태':<6} | {'아이디어 내용'}")
    print("----------------------------------------------------------------------------------")
    for i in filtered:
        status_symbol = "🟢 TODO" if i.get("status") == "TODO" else "🔴 DONE"
        print(f"{i['id']:<4} | {i['date']:<19} | {status_symbol:<6} | {i['text']}")
    print("==================================================================================\n")

def complete_idea(idea_id):
    """아이디어 완료 처리"""
    ideas = load_ideas()
    found = False
    for i in ideas:
        if i.get("id") == idea_id:
            i["status"] = "DONE"
            found = True
            print(f"✅ [Memo Manager] 아이디어가 완료 처리되었습니다: ID {idea_id} -> '{i['text']}'")
            break
            
    if found:
        save_ideas(ideas)
    else:
        print(f"❌ [Memo Manager] ID {idea_id}에 해당하는 아이디어를 찾지 못했습니다.")

def delete_idea(idea_id):
    """아이디어 삭제 처리"""
    ideas = load_ideas()
    original_len = len(ideas)
    ideas = [i for i in ideas if i.get("id") != idea_id]
    
    if len(ideas) < original_len:
        save_ideas(ideas)
        print(f"🗑️ [Memo Manager] 아이디어가 삭제되었습니다: ID {idea_id}")
    else:
        print(f"❌ [Memo Manager] ID {idea_id}에 해당하는 아이디어를 찾지 못했습니다.")

def main():
    parser = argparse.ArgumentParser(description="KBO 글감 아이디어 관리 매니저")
    parser.add_argument("--add", type=str, help="새로운 기획 아이디어 추가")
    parser.add_argument("--list", action="store_true", help="미완료 아이디어 목록 조회")
    parser.add_argument("--all", action="store_true", help="완료된 항목을 포함해 전체 목록 조회")
    parser.add_argument("--complete", type=int, help="특정 ID의 아이디어를 완료(DONE)로 처리")
    parser.add_argument("--delete", type=int, help="특정 ID의 아이디어 삭제")
    
    args = parser.parse_args()
    
    if args.add:
        add_idea(args.add)
    elif args.list or args.all:
        list_ideas(show_all=args.all)
    elif args.complete is not None:
        complete_idea(args.complete)
    elif args.delete is not None:
        delete_idea(args.delete)
    else:
        # 인자가 없으면 기본적으로 list_ideas 구동
        list_ideas(show_all=False)

if __name__ == "__main__":
    main()
