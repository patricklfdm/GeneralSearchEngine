package org.example.generalsearch.catalog;

import org.example.generalsearch.model.Product;

final class ProductBlock {
    static final int SIZE = 1024;

    private final Product[] products;

    private ProductBlock(Product[] products) {
        this.products = products;
    }

    static ProductBlock empty() {
        return new ProductBlock(new Product[SIZE]);
    }

    static ProductBlock owned(Product[] products) {
        return new ProductBlock(products);
    }

    Product get(int offset) {
        return products[offset];
    }

    ProductBlock with(int offset, Product product) {
        if (products[offset] == product) {
            return this;
        }
        Product[] copy = products.clone();
        copy[offset] = product;
        return new ProductBlock(copy);
    }

    Product[] copyProducts() {
        return products.clone();
    }
}
