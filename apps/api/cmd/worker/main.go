package main

import "log"

func main() {
	// This executable is intentionally separate from the HTTP API.
	// Railway cron/scheduled jobs can run individual job commands later.
	log.Println("YAFA VANAM worker scaffold ready")
}
