package io.github.patricklfdm.generalsearch.engine;

import io.github.patricklfdm.generalsearch.model.Product;

/** Product-specialized view of the generic search engine API. */
public interface ProductSearchEngine extends SearchEngine<String, Product> {}
