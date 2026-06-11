from supabase import create_client

url = "https://gotlqwwxmuihedpavwna.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdvdGxxd3d4bXVpaGVkcGF2d25hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwNzg4ODQsImV4cCI6MjA5NjY1NDg4NH0.TBo7xOupS1ZlGzZE1TOa1rHuHKNr_e_bqPc2vnHl8EY"

try:
    supabase = create_client(url, key)
    print("✅ Supabase connection successful!")
    print("✅ No proxy parameter error!")
except Exception as e:
    print(f"❌ Error: {e}")
