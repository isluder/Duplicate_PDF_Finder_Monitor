import os
import sys
import time
import hashlib
import shutil
import argparse

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: 'watchdog' library is not installed.")
    print("Please install it using: pip install watchdog")
    sys.exit(1)


def get_file_hash(filepath, block_size=65536):
    """Calculates the SHA-256 hash of a file to uniquely identify its contents."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                hasher.update(block)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

class DuplicatePDFHandler(FileSystemEventHandler):
    def __init__(self, watch_dir):
        super().__init__()
        self.watch_dir = watch_dir
        self.duplicates_dir = os.path.join(watch_dir, 'duplicates_found')
        os.makedirs(self.duplicates_dir, exist_ok=True)
        self.seen_hashes = {}  # Maps file_hash -> filepath
        self.file_to_hash = {}  # Reverse map: filepath -> file_hash
        self._recently_processed = {}  # filepath -> timestamp, for debouncing duplicate events
        self.scan_existing_files()

    def _is_in_duplicates_dir(self, filepath):
        """Return True if filepath is inside the duplicates_found subdirectory."""
        return os.path.abspath(filepath).startswith(os.path.abspath(self.duplicates_dir))

    def scan_existing_files(self):
        print(f"Scanning existing PDFs in '{self.watch_dir}' for duplicates...")
        # Sort files so we keep the first one alphabetically and move subsequent identical ones
        files = sorted(os.listdir(self.watch_dir))
        
        for filename in files:
            if filename.lower().endswith('.pdf'):
                filepath = os.path.join(self.watch_dir, filename)
                if os.path.isfile(filepath) and not self._is_in_duplicates_dir(filepath):
                    file_hash = get_file_hash(filepath)
                    if file_hash:
                        if file_hash in self.seen_hashes:
                            original_path = self.seen_hashes[file_hash]
                            print(f"[-] Found existing duplicate: '{filename}' (matches '{os.path.basename(original_path)}'). Moving to duplicates_found/...")
                            self.move_to_duplicates(filepath)
                        else:
                            self.seen_hashes[file_hash] = filepath
                            self.file_to_hash[filepath] = file_hash
                            
        print(f"Initial scan complete. {len(self.seen_hashes)} unique PDFs found.")
        print(f"Duplicates will be moved to: '{self.duplicates_dir}'")
        print(f"Now monitoring '{self.watch_dir}' for new PDFs...")

    def move_to_duplicates(self, filepath):
        """Move a duplicate file to the duplicates_found/ subdirectory."""
        try:
            basename = os.path.basename(filepath)
            dest = os.path.join(self.duplicates_dir, basename)
            # If a file with the same name already exists in duplicates_found, add a counter
            if os.path.exists(dest):
                name, ext = os.path.splitext(basename)
                counter = 1
                while os.path.exists(dest):
                    dest = os.path.join(self.duplicates_dir, f"{name}_{counter}{ext}")
                    counter += 1
            shutil.move(filepath, dest)
            print(f"    -> Moved to duplicates_found/: {os.path.basename(dest)}")
        except Exception as e:
            print(f"    -> Failed to move {os.path.basename(filepath)}: {e}")

    def on_created(self, event):
        # We only care about file creations, specifically PDFs (ignore duplicates_found subdir)
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            if not self._is_in_duplicates_dir(event.src_path):
                self.process_new_file(event.src_path)

    def on_moved(self, event):
        # Handle cases where a file is moved/renamed into the directory
        if not event.is_directory:
            # Evict the old path from tracking so a rename isn't flagged as its own duplicate
            if event.src_path in self.file_to_hash:
                old_hash = self.file_to_hash.pop(event.src_path)
                if self.seen_hashes.get(old_hash) == event.src_path:
                    del self.seen_hashes[old_hash]

            # Process the destination as a new file if it's a PDF (ignore duplicates_found subdir)
            if event.dest_path.lower().endswith('.pdf') and not self._is_in_duplicates_dir(event.dest_path):
                self.process_new_file(event.dest_path)

    def on_deleted(self, event):
        """Evict deleted files from the hash map so it stays in sync with the filesystem."""
        if not event.is_directory and event.src_path in self.file_to_hash:
            deleted_hash = self.file_to_hash.pop(event.src_path)
            if self.seen_hashes.get(deleted_hash) == event.src_path:
                del self.seen_hashes[deleted_hash]
                print(f"[x] Tracked PDF removed: {os.path.basename(event.src_path)}")

    def process_new_file(self, filepath):
        # Debounce: macOS FSEvents can fire multiple events for a single file copy.
        # Skip if we already processed this exact filepath within the last 3 seconds.
        now = time.time()
        last_processed = self._recently_processed.get(filepath, 0)
        if now - last_processed < 3:
            return
        self._recently_processed[filepath] = now

        print(f"[+] New PDF detected: {os.path.basename(filepath)}")
        
        # Wait slightly to ensure the file has finished writing/copying
        time.sleep(1) 
        
        # Verify file size has stopped changing (important for large files / network copies)
        previous_size = -1
        retries = 20  # Up to ~10 seconds of waiting for the file to stabilize
        while retries > 0:
            try:
                current_size = os.path.getsize(filepath)
                if current_size == previous_size and current_size > 0:
                    break
                previous_size = current_size
                time.sleep(0.5)
                retries -= 1
            except OSError:
                break

        if retries == 0:
            print(f"    -> Warning: '{os.path.basename(filepath)}' may still be writing. Skipping for now (will catch on next event or restart).")
            return  # CRITICAL FIX: do NOT hash a partially-written file
                
        if not os.path.exists(filepath):
            return

        file_hash = get_file_hash(filepath)
        if file_hash:
            if file_hash in self.seen_hashes:
                original_path = self.seen_hashes[file_hash]
                # If the hash maps to the same file, it's a duplicate event, not a duplicate file
                if os.path.abspath(original_path) == os.path.abspath(filepath):
                    return
                print(f"[-] Duplicate detected! '{os.path.basename(filepath)}' is a duplicate of '{os.path.basename(original_path)}'.")
                self.move_to_duplicates(filepath)
            else:
                self.seen_hashes[file_hash] = filepath
                self.file_to_hash[filepath] = file_hash
                print(f"[+] Added new unique PDF: {os.path.basename(filepath)}")


def main():
    parser = argparse.ArgumentParser(description="Monitor a folder for duplicate PDFs and remove them efficiently.")
    parser.add_argument('folder', type=str, nargs='?', default='.', help='The path to the folder to monitor (defaults to current directory)')
    args = parser.parse_args()

    watch_dir = os.path.abspath(args.folder)

    if not os.path.exists(watch_dir):
        print(f"Error: The directory {watch_dir} does not exist.")
        sys.exit(1)
    if not os.path.isdir(watch_dir):
        print(f"Error: {watch_dir} is not a directory.")
        sys.exit(1)

    event_handler = DuplicatePDFHandler(watch_dir)
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=True)  # recursive to catch events in subdirs (so we can ignore duplicates_found)
    observer.start()
    
    print("\nPress Ctrl+C to stop monitoring.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Shutting down gracefully...")
        observer.stop()
    
    observer.join()
    print("Program terminated.")

if __name__ == "__main__":
    main()
