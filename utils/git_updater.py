import os
import hashlib
from git import Repo
from github import Github
from tqdm import tqdm

# === KONFIGURACJA ===
LOCAL_REPO_PATH = "D:\\SocialFlow"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Token osobisty z uprawnieniami do repo
GITHUB_REPO_NAME = "DragosOficial/SocialFlow"  # np. "DawidWielechowski/moje-repo"
BRANCH_NAME = "main"

def file_hash(filepath):
    """Zwraca hash SHA-1 pliku"""
    with open(filepath, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()

def get_remote_file_hashes(repo, branch):
    """Zwraca dict {ścieżka: hash_sha1} dla plików z GitHuba"""
    print("Pobieranie listy plików z GitHuba...")
    try:
        contents = repo.get_contents("", ref=branch)
    except Exception as e:
        print(f"Nie udało się pobrać zawartości repo: {e}")
        return {}

    file_hashes = {}
    stack = contents[:]
    all_files = []

    try:
        while stack:
            file = stack.pop()
            if file.type == "dir":
                stack.extend(repo.get_contents(file.path, ref=branch))
            else:
                all_files.append(file)

        for file in tqdm(all_files, desc="Pobieranie zdalnych hashy", unit="plik"):
            file_hashes[file.path] = hashlib.sha1(file.decoded_content).hexdigest()

    except Exception as e:
        print(f"Błąd podczas pobierania plików zdalnych: {e}")
        return {}

    return file_hashes

def get_local_file_hashes(folder):
    """Zwraca dict {sciezka_wzgledem_folderu: hash}, pomijając build/ i dist/"""
    local_hashes = {}
    for root, dirs, files in os.walk(folder):
        # Pomijaj foldery build i dist
        # Pomijaj foldery build, dist oraz __pycache__
        dirs[:] = [d for d in dirs if d not in ('build', 'dist', '.git', 'tools')]

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, folder)
            rel_path_unix = rel_path.replace("\\", "/")  # Windows compatibility

            #if rel_path_unix == "utils/git_updater.py":
            #    continue  # Pomiń sam skrypt aktualizujący
        
            local_hashes[rel_path_unix] = file_hash(full_path)
    return local_hashes

def update_repo_and_push():
    print("Łączenie z GitHubem...")
    gh = Github(GITHUB_TOKEN)
    repo_remote = gh.get_repo(GITHUB_REPO_NAME)

    print("Pobieranie plików z GitHuba...")
    remote_hashes = get_remote_file_hashes(repo_remote, BRANCH_NAME)
    local_hashes = get_local_file_hashes(LOCAL_REPO_PATH)

    changed_files = []
    for path, local_hash in local_hashes.items():
        if path not in remote_hashes or remote_hashes[path] != local_hash:
            changed_files.append(path)

    if not changed_files:
        print("Brak zmian do przesłania.")
        return

    print("Zmienione pliki:")
    for f in changed_files:
        print(f" - {f}")

    # Commit i push
    print("Commitowanie i wysyłanie zmian...")
    repo_local = Repo(LOCAL_REPO_PATH)
    repo_local.git.pull('origin', BRANCH_NAME, '--allow-unrelated-histories')
    repo_local.index.add(changed_files)
    repo_local.index.commit("Automatyczna aktualizacja zmienionych plików")
    origin = repo_local.remote(name='origin')
    origin.push(refspec=f"{repo_local.active_branch.name}:{BRANCH_NAME}")
    print("Zakończono!")

if __name__ == "__main__":
    update_repo_and_push()
