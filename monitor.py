import os
import sys
import time
import hashlib
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
        self.seen_hashes = {}  # Maps file_hash -> filepath
        self.scan_existing_files()

    def scan_existing_files(self):
        print(f"Scanning existing PDFs in '{self.watch_dir}' for duplicates...")
        # Sort files so we keep the first one alphabetically and delete subsequent identical ones
        files = sorted(os.listdir(self.watch_dir))
        
        for filename in files:
            if filename.lower().endswith('.pdf'):
                filepath = os.path.join(self.watch_dir, filename)
                if os.path.isfile(filepath):
                    file_hash = get_file_hash(filepath)
                    if file_hash:
                        if file_hash in self.seen_hashes:
                            original_path = self.seen_hashes[file_hash]
                            print(f"[-] Found existing duplicate: '{filename}' (matches '{os.path.basename(original_path)}'). Removing...")
                            self.remove_file(filepath)
                        else:
                            self.seen_hashes[file_hash] = filepath
                            
        print(f"Initial scan complete. {len(self.seen_hashes)} unique PDFs found.")
        print(f"Now monitoring '{self.watch_dir}' for new PDFs...")

    def remove_file(self, filepath):
        try:
            os.remove(filepath)
            print(f"    -> Successfully deleted: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"    -> Failed to delete {os.path.basename(filepath)}: {e}")

    def on_created(self, event):
        # We only care about file creations, specifically PDFs
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self.process_new_file(event.src_path)

    def on_moved(self, event):
        # Handle cases where a file is moved/renamed into the directory
        if not event.is_directory and event.dest_path.lower().endswith('.pdf'):
            self.process_new_file(event.dest_path)

    def process_new_file(self, filepath):
        print(f"[+] New PDF detected: {os.path.basename(filepath)}")
        
        # Wait slightly to ensure the file has finished writing/copying
        time.sleep(1) 
        
        # Verify file size has stopped changing (simple check for large files)
        previous_size = -1
        retries = 10
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
                
        if not os.path.exists(filepath):
            return

        file_hash = get_file_hash(filepath)
        if file_hash:
            if file_hash in self.seen_hashes:
                original_path = self.seen_hashes[file_hash]
                print(f"[-] Duplicate detected! '{os.path.basename(filepath)}' is a duplicate of '{os.path.basename(original_path)}'.")
                self.remove_file(filepath)
            else:
                self.seen_hashes[file_hash] = filepath
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
    observer.schedule(event_handler, watch_dir, recursive=False)
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
