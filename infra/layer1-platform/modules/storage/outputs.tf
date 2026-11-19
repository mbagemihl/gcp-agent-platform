output "rag_bucket_name" {
  description = "Name of the GCS bucket containing policy source files"
  value       = google_storage_bucket.rag_documents.name
}

output "firestore_database_name" {
  description = "Name of the Firestore Native database"
  value       = google_firestore_database.compliance_db.name
}

output "policy_files_hash" {
  description = "Deterministic hash over uploaded policy objects to re-trigger RAG seeding on changes"
  value = sha256(join(",", [
    for key in sort(keys(google_storage_bucket_object.policy_documents)) :
    "${key}:${google_storage_bucket_object.policy_documents[key].md5hash}"
  ]))
}
