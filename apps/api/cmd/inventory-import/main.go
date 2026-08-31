package main

import (
	"context"
	"encoding/csv"
	"errors"
	"flag"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type inventoryRow struct {
	variantID, reason string
	onHand, threshold int
}

func main() {
	filePath := flag.String("file", "../../data/inventory/initial-stock.csv", "inventory CSV")
	apply := flag.Bool("apply", false, "write validated counts to DATABASE_URL")
	actor := flag.String("actor", "inventory-import", "audit actor")
	flag.Parse()
	rows, err := readRows(*filePath)
	if err != nil {
		fatal(err)
	}
	fmt.Printf("Validated %d unique inventory rows.\n", len(rows))
	if !*apply {
		fmt.Println("Dry run only. Pass -apply with DATABASE_URL to update inventory.")
		return
	}
	databaseURL := strings.TrimSpace(os.Getenv("DATABASE_URL"))
	if databaseURL == "" {
		fatal(errors.New("DATABASE_URL is required with -apply"))
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		fatal(err)
	}
	defer pool.Close()
	tx, err := pool.Begin(ctx)
	if err != nil {
		fatal(err)
	}
	defer tx.Rollback(ctx)
	for _, row := range rows {
		var previous, reserved int
		err := tx.QueryRow(ctx,
			`SELECT on_hand_quantity, reserved_quantity FROM inventory_levels WHERE variant_id=$1 FOR UPDATE`,
			row.variantID).Scan(&previous, &reserved)
		if err != nil {
			fatal(fmt.Errorf("variant %s is not synchronized: %w", row.variantID, err))
		}
		if row.onHand < reserved {
			fatal(fmt.Errorf("variant %s has %d reserved units and cannot be reduced to %d", row.variantID, reserved, row.onHand))
		}
		if _, err := tx.Exec(ctx,
			`UPDATE inventory_levels SET on_hand_quantity=$2, low_stock_threshold=$3,
			 low_stock_alerted=CASE WHEN $2-reserved_quantity > $3 THEN FALSE ELSE low_stock_alerted END,
			 version=version+1, updated_at=NOW() WHERE variant_id=$1`, row.variantID, row.onHand, row.threshold); err != nil {
			fatal(err)
		}
		if delta := row.onHand - previous; delta != 0 {
			if _, err := tx.Exec(ctx,
				`INSERT INTO inventory_movements
				 (variant_id, movement_type, quantity_delta, reason, actor)
				 VALUES ($1, 'ADJUSTMENT', $2, $3, $4)`, row.variantID, delta, row.reason, *actor); err != nil {
				fatal(err)
			}
		}
	}
	if err := tx.Commit(ctx); err != nil {
		fatal(err)
	}
	fmt.Printf("Applied %d inventory rows with an audit trail.\n", len(rows))
}

func readRows(path string) ([]inventoryRow, error) {
	handle, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer handle.Close()
	reader := csv.NewReader(handle)
	records, err := reader.ReadAll()
	if err != nil || len(records) < 2 {
		return nil, errors.New("inventory CSV is empty or invalid")
	}
	columns := map[string]int{}
	for index, name := range records[0] {
		columns[strings.TrimSpace(name)] = index
	}
	for _, required := range []string{"variant_id", "on_hand_quantity", "low_stock_threshold", "reason"} {
		if _, ok := columns[required]; !ok {
			return nil, fmt.Errorf("missing %s column", required)
		}
	}
	seen := map[string]bool{}
	rows := make([]inventoryRow, 0, len(records)-1)
	for number, record := range records[1:] {
		get := func(name string) string { return strings.TrimSpace(record[columns[name]]) }
		variantID := get("variant_id")
		if variantID == "" || seen[variantID] {
			return nil, fmt.Errorf("row %d has an empty or duplicate variant_id", number+2)
		}
		onHand, err := strconv.Atoi(get("on_hand_quantity"))
		if err != nil || onHand < 0 {
			return nil, fmt.Errorf("row %d has invalid on_hand_quantity", number+2)
		}
		threshold, err := strconv.Atoi(get("low_stock_threshold"))
		if err != nil || threshold < 0 {
			return nil, fmt.Errorf("row %d has invalid low_stock_threshold", number+2)
		}
		reason := get("reason")
		if reason == "" {
			return nil, fmt.Errorf("row %d requires an audit reason", number+2)
		}
		seen[variantID] = true
		rows = append(rows, inventoryRow{variantID: variantID, onHand: onHand, threshold: threshold, reason: reason})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].variantID < rows[j].variantID })
	return rows, nil
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "inventory import:", err)
	os.Exit(1)
}
