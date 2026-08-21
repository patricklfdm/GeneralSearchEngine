package org.example.generalsearch.engine;

import org.example.generalsearch.model.Product;

/** Product-specialized view of the generic search engine API. */
public interface ProductSearchEngine extends SearchEngine<String, Product> {}
