package commerce

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Description struct {
	Short string `json:"short"`
	Full  string `json:"full"`
}

type Commerce struct {
	Currency       string   `json:"currency"`
	BasePrice      float64  `json:"base_price"`
	CompareAtPrice *float64 `json:"compare_at_price"`
}

type Shade struct {
	Name      string  `json:"name"`
	Code      *string `json:"code"`
	Hex       *string `json:"hex"`
	Undertone *string `json:"undertone"`
}

type Variant struct {
	ID       string  `json:"id"`
	SKU      *string `json:"sku"`
	Size     *string `json:"size"`
	Shade    *Shade  `json:"shade"`
	Price    float64 `json:"price"`
	Stock    *int    `json:"stock"`
	IsActive bool    `json:"is_active"`
}

type Images struct {
	Primary       *string  `json:"primary"`
	Gallery       []string `json:"gallery"`
	Lifestyle     []string `json:"lifestyle"`
	Detail        []string `json:"detail"`
	Texture       *string  `json:"texture"`
	Alt           string   `json:"alt"`
	PathsVerified bool     `json:"paths_verified"`
}

type Usage struct {
	HowToUse string   `json:"how_to_use"`
	Amount   *string  `json:"amount"`
	When     []string `json:"when"`
}

type Ingredients struct {
	FullINCI          *string `json:"full_inci"`
	ActiveIngredients []any   `json:"active_ingredients"`
	IngredientNote    *string `json:"ingredient_data_note"`
}

type Product struct {
	ID          string      `json:"id"`
	Name        string      `json:"name"`
	Slug        string      `json:"slug"`
	Brand       string      `json:"brand"`
	Category    string      `json:"category"`
	Subcategory string      `json:"subcategory"`
	ProductType string      `json:"product_type"`
	Status      string      `json:"status"`
	Description Description `json:"description"`
	Commerce    Commerce    `json:"commerce"`
	Variants    []Variant   `json:"variants"`
	Images      Images      `json:"images"`
	Benefits    []string    `json:"benefits"`
	Usage       Usage       `json:"usage"`
	Warnings    []string    `json:"warnings"`
	Ingredients Ingredients `json:"ingredients"`
}

type ProductList struct {
	Items  []*Product `json:"items"`
	Total  int        `json:"total"`
	Limit  int        `json:"limit"`
	Offset int        `json:"offset"`
}

type ProductFilter struct {
	Category    string
	Subcategory string
	Query       string
	Limit       int
	Offset      int
}

type Category struct {
	Name          string   `json:"name"`
	Subcategories []string `json:"subcategories"`
	ProductCount  int      `json:"product_count"`
}

type Catalog struct {
	products   []*Product
	byID       map[string]*Product
	bySlug     map[string]*Product
	variants   map[string]variantRef
	categories []Category
}

type variantRef struct {
	product *Product
	variant *Variant
}

var ErrProductNotFound = errors.New("product not found")
var ErrVariantNotFound = errors.New("variant not found")
var ErrVariantUnavailable = errors.New("variant unavailable")
var ErrInsufficientStock = errors.New("requested quantity exceeds available stock")

func LoadCatalog(path string) (*Catalog, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open catalogue: %w", err)
	}
	defer file.Close()
	return DecodeCatalog(file)
}

func DecodeCatalog(reader io.Reader) (*Catalog, error) {
	var products []*Product
	decoder := json.NewDecoder(reader)
	if err := decoder.Decode(&products); err != nil {
		return nil, fmt.Errorf("decode catalogue: %w", err)
	}
	if len(products) == 0 {
		return nil, errors.New("catalogue contains no products")
	}

	catalog := &Catalog{
		byID:     make(map[string]*Product, len(products)),
		bySlug:   make(map[string]*Product, len(products)),
		variants: make(map[string]variantRef),
	}
	categorySets := make(map[string]map[string]struct{})
	categoryCounts := make(map[string]int)

	for _, product := range products {
		if !strings.EqualFold(product.Status, "active") {
			continue
		}
		if strings.TrimSpace(product.ID) == "" || strings.TrimSpace(product.Slug) == "" {
			return nil, errors.New("active product is missing id or slug")
		}
		if _, exists := catalog.byID[product.ID]; exists {
			return nil, fmt.Errorf("duplicate product id %q", product.ID)
		}
		if _, exists := catalog.bySlug[product.Slug]; exists {
			return nil, fmt.Errorf("duplicate product slug %q", product.Slug)
		}
		if product.Commerce.Currency == "" {
			product.Commerce.Currency = "INR"
		}
		catalog.products = append(catalog.products, product)
		catalog.byID[product.ID] = product
		catalog.bySlug[product.Slug] = product
		categoryCounts[product.Category]++
		if categorySets[product.Category] == nil {
			categorySets[product.Category] = make(map[string]struct{})
		}
		if product.Subcategory != "" {
			categorySets[product.Category][product.Subcategory] = struct{}{}
		}
		for index := range product.Variants {
			variant := &product.Variants[index]
			if variant.ID == "" {
				return nil, fmt.Errorf("product %q has a variant without an id", product.ID)
			}
			if _, exists := catalog.variants[variant.ID]; exists {
				return nil, fmt.Errorf("duplicate variant id %q", variant.ID)
			}
			catalog.variants[variant.ID] = variantRef{product: product, variant: variant}
		}
	}

	if len(catalog.products) == 0 {
		return nil, errors.New("catalogue contains no active products")
	}
	sort.Slice(catalog.products, func(i, j int) bool { return catalog.products[i].Name < catalog.products[j].Name })
	for name, values := range categorySets {
		subcategories := make([]string, 0, len(values))
		for value := range values {
			subcategories = append(subcategories, value)
		}
		sort.Strings(subcategories)
		catalog.categories = append(catalog.categories, Category{
			Name: name, Subcategories: subcategories, ProductCount: categoryCounts[name],
		})
	}
	sort.Slice(catalog.categories, func(i, j int) bool { return catalog.categories[i].Name < catalog.categories[j].Name })
	return catalog, nil
}

func ResolveCatalogPath(configured string) (string, error) {
	configured = strings.TrimSpace(configured)
	if configured != "" {
		if path, err := existingFile(configured); err == nil {
			return path, nil
		}
		return "", fmt.Errorf("configured catalogue %q does not exist", configured)
	}

	candidates := []string{
		filepath.Join("data", "processed", "Product.json"),
		filepath.Join("..", "..", "data", "processed", "Product.json"),
		filepath.Join("..", "data", "processed", "Product.json"),
		filepath.Join("/app", "data", "processed", "Product.json"),
	}
	if executable, err := os.Executable(); err == nil {
		base := filepath.Dir(executable)
		candidates = append(candidates,
			filepath.Join(base, "data", "processed", "Product.json"),
			filepath.Join(base, "..", "data", "processed", "Product.json"),
		)
	}
	for _, candidate := range candidates {
		if path, err := existingFile(candidate); err == nil {
			return path, nil
		}
	}
	return "", errors.New("catalogue not found; set YAFA_CATALOGUE_PATH")
}

func existingFile(path string) (string, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	info, err := os.Stat(absolute)
	if err != nil || info.IsDir() {
		return "", errors.New("not a file")
	}
	return absolute, nil
}

func (catalog *Catalog) ProductCount() int { return len(catalog.products) }

func (catalog *Catalog) Categories() []Category {
	return append([]Category(nil), catalog.categories...)
}

func (catalog *Catalog) ProductByID(id string) (*Product, error) {
	product, ok := catalog.byID[id]
	if !ok {
		return nil, ErrProductNotFound
	}
	return product, nil
}

func (catalog *Catalog) ProductBySlug(slug string) (*Product, error) {
	product, ok := catalog.bySlug[slug]
	if !ok {
		return nil, ErrProductNotFound
	}
	return product, nil
}

func (catalog *Catalog) SellableVariant(productID, variantID string) (*Product, *Variant, error) {
	ref, ok := catalog.variants[variantID]
	if !ok || ref.product.ID != productID {
		return nil, nil, ErrVariantNotFound
	}
	if !ref.variant.IsActive || (ref.variant.Stock != nil && *ref.variant.Stock <= 0) {
		return nil, nil, ErrVariantUnavailable
	}
	return ref.product, ref.variant, nil
}

func (catalog *Catalog) List(filter ProductFilter) ProductList {
	if filter.Limit <= 0 || filter.Limit > 100 {
		filter.Limit = 24
	}
	if filter.Offset < 0 {
		filter.Offset = 0
	}
	query := strings.ToLower(strings.TrimSpace(filter.Query))
	items := make([]*Product, 0)
	for _, product := range catalog.products {
		if filter.Category != "" && !strings.EqualFold(filter.Category, product.Category) {
			continue
		}
		if filter.Subcategory != "" && !strings.EqualFold(filter.Subcategory, product.Subcategory) {
			continue
		}
		if query != "" {
			haystack := strings.ToLower(strings.Join([]string{
				product.Name, product.Category, product.Subcategory, product.ProductType,
				product.Description.Short, strings.Join(product.Benefits, " "),
			}, " "))
			if !strings.Contains(haystack, query) {
				continue
			}
		}
		items = append(items, product)
	}
	total := len(items)
	if filter.Offset >= total {
		items = []*Product{}
	} else {
		end := min(filter.Offset+filter.Limit, total)
		items = items[filter.Offset:end]
	}
	return ProductList{Items: items, Total: total, Limit: filter.Limit, Offset: filter.Offset}
}
