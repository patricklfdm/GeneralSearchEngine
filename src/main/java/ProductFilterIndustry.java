import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.function.BiConsumer;
import java.util.function.IntConsumer;

public class ProductFilterIndustry {

    // region Product
    enum Category {
        ELECTRONICS,
        BOOKS,
        CLOTHING,
        HOME,
        BEAUTY
    }

    record Product(
            String id,
            String name,
            Category category,
            double price,
            boolean prime,
            double rating
    ){
        Product {
            Utils.validateProd(id, name, category, price, rating);
        }
    }
    // endregion

    // region Trie
    static class Trie {

        static class TrieNode {
            private final Map<Character, TrieNode> children;
            private final BitSet prefixSet;

            TrieNode() {
                this.children = new HashMap<>();
                this.prefixSet = new BitSet();
            }

            public BitSet getPrefixSet(){
                return (BitSet) this.prefixSet.clone();
            }
        }

        TrieNode root;

        Trie(){
            root = new TrieNode();
        }

        void insert(String word, int docId){
            Utils.validateStr(word);
            char[] arr = word.toCharArray();
            TrieNode node = this.root;
            for(char c : arr){
                node = node.children.computeIfAbsent(c, k -> new TrieNode());
                node.prefixSet.set(docId);
            }
        }

        boolean remove(String word, int docId){
            Utils.validateStr(word);
            char[] arr = word.toCharArray();
            TrieNode node = this.root;
            for(char c : arr){
                node = node.children.get(c);
                if(node == null){
                    return false;
                }
                node.prefixSet.clear(docId);
            }
            return true;
        }

        BitSet getPrefixSet(String word){
            Utils.validateStr(word);
            char[] arr = word.toCharArray();
            TrieNode node = this.root;
            for(char c : arr){
                node = node.children.get(c);
                if(node == null){
                    return null;
                }
            }
            return node.getPrefixSet();
        }
    }
    // endregion

    // region Index

    interface ProductIndex {
        void add(Product product, int docId);
        void remove(Product product, int docId);
        void update(Product oldProduct, Product newProduct, int docId);
        Optional<BitSet> getCandidates(ProductFilter filter);
    }
    static class NamePrefixIndex implements ProductIndex {

        private final Trie prefixIndex;

        NamePrefixIndex() {
            this.prefixIndex = new Trie();
        }

        @Override
        public void add(Product product, int docId) {
            this.prefixIndex.insert(product.name(), docId);
        }

        @Override
        public void remove(Product product, int docId) {
            this.prefixIndex.remove(product.name(), docId);
        }

        @Override
        public void update(Product oldProduct, Product newProduct, int docId) {
            if (!oldProduct.name().equals(newProduct.name())) {
                remove(oldProduct, docId);
                add(newProduct, docId);
            }
        }

        @Override
        public Optional<BitSet> getCandidates(ProductFilter filter) {
            if(filter instanceof NameFilter nameFilter){
                return Optional.of(getByPrefix(nameFilter.prefix()));
            }
            return Optional.empty();
        }

        private BitSet getByPrefix(String prefix){
            BitSet bits = this.prefixIndex.getPrefixSet(prefix);
            return bits == null ? new BitSet() : bits;
        }
    }
    static class CategoryIndex implements ProductIndex {

        private final Map<Category, BitSet> categoryIndex;

        CategoryIndex() {
            this.categoryIndex = new HashMap<>();
        }

        @Override
        public void add(Product product, int docId) {
            this.categoryIndex
                    .computeIfAbsent(
                            product.category(),
                            k -> new BitSet()
                    )
                    .set(docId);
        }

        @Override
        public void remove(Product product, int docId) {
            BitSet categoryBits = this.categoryIndex.get(product.category());
            categoryBits.clear(docId);
            if (categoryBits.isEmpty()) {
                this.categoryIndex.remove(product.category());
            }
        }

        @Override
        public void update(Product oldProduct, Product newProduct, int docId) {
            if (oldProduct.category() != newProduct.category()) {
                remove(oldProduct, docId);
                add(newProduct, docId);
            }
        }

        @Override
        public Optional<BitSet> getCandidates(ProductFilter filter) {
            if(filter instanceof CategoryFilter categoryFilter){
                return Optional.of(getByCategory(categoryFilter.category()));
            }
            return Optional.empty();
        }

        private BitSet getByCategory(Category category) {
            BitSet bits = this.categoryIndex.get(category);
            if(bits == null){
                return new BitSet();
            }
            return (BitSet) bits.clone();
        }
    }
    static class PrimeIndex implements ProductIndex {

        private final Map<Boolean, BitSet> primeIndex;

        PrimeIndex() {
            this.primeIndex = new HashMap<>();
        }

        @Override
        public void add(Product product, int docId) {
            this.primeIndex
                    .computeIfAbsent(
                            product.prime(),
                            k -> new BitSet()
                    )
                    .set(docId);
        }

        @Override
        public void remove(Product product, int docId) {
            BitSet primeBits = this.primeIndex.get(product.prime());
            primeBits.clear(docId);
            if (primeBits.isEmpty()) {
                this.primeIndex.remove(product.prime());
            }
        }

        @Override
        public void update(Product oldProduct, Product newProduct, int docId) {
            if (oldProduct.prime() != newProduct.prime()) {
                remove(oldProduct, docId);
                add(newProduct, docId);
            }
        }

        @Override
        public Optional<BitSet> getCandidates(ProductFilter filter) {
            if(filter instanceof PrimeFilter primeFilter) {
                return Optional.of(getByPrime(primeFilter.requirePrime()));
            }
            return Optional.empty();
        }

        private BitSet getByPrime(boolean prime) {
            BitSet bits = this.primeIndex.get(prime);
            if(bits == null){
                return new BitSet();
            }
            return (BitSet) bits.clone();
        }
    }
    static class PriceIndex implements ProductIndex {

        private final TreeMap<Double, BitSet> priceIndex;

        PriceIndex() {
            this.priceIndex = new TreeMap<>();
        }

        @Override
        public void add(Product product, int docId) {
            this.priceIndex
                    .computeIfAbsent(
                            product.price(),
                            k -> new BitSet()
                    )
                    .set(docId);
        }

        @Override
        public void remove(Product product, int docId) {
            BitSet priceBits = priceIndex.get(product.price());
            priceBits.clear(docId);
            if (priceBits.isEmpty()) {
                priceIndex.remove(product.price());
            }
        }

        @Override
        public void update(Product oldProduct, Product newProduct, int docId) {
            if (Double.compare(
                    oldProduct.price(),
                    newProduct.price()
            ) != 0) {
                remove(oldProduct, docId);
                add(newProduct, docId);
            }
        }

        @Override
        public Optional<BitSet> getCandidates(ProductFilter filter) {
            if(filter instanceof PriceRangeFilter priceRangeFilter){
                return Optional.of(
                        getByPriceRange(
                                priceRangeFilter.minPrice(),
                                priceRangeFilter.maxPrice()
                        )
                );
            }
            return Optional.empty();
        }

        private BitSet getByPriceRange(
                double minPrice,
                double maxPrice
        ) {
            NavigableMap<Double, BitSet> sets = this.priceIndex.subMap(
                    minPrice, true, maxPrice, true);
            BitSet res = new BitSet();
            for(BitSet bits : sets.values()){
                res.or(bits);
            }
            return res;
        }
    }

    // endregion

    // region PersistentBlockTree

    static final class BlockTreeNode {

        private static final int BRANCHING = 32;

        private final Object[] children;

        private BlockTreeNode(Object[] children) {
            this.children = children;
        }

        static BlockTreeNode empty() {
            return new BlockTreeNode(
                    new Object[BRANCHING]
            );
        }

        static BlockTreeNode fromOwnedChildren(
                Object[] children
        ) {
            return new BlockTreeNode(children);
        }
    }
    static final class PersistentBlockTree<T> {

        private static final int BRANCHING = 32;
        private static final int BITS = 5;
        private static final int MASK = BRANCHING - 1;

        private final BlockTreeNode root;
        private final int shift;

        PersistentBlockTree() {
            this.root = BlockTreeNode.empty();
            this.shift = 0;
        }

        private PersistentBlockTree(
                BlockTreeNode root,
                int shift
        ) {
            this.root = root;
            this.shift = shift;
        }

        static <T> PersistentBlockTree<T> fromOwnedRoot(
                BlockTreeNode root,
                int shift
        ) {
            return new PersistentBlockTree<>(
                    root,
                    shift
            );
        }

        BlockTreeNode root() {
            return root;
        }

        int shift() {
            return shift;
        }

        @SuppressWarnings("unchecked")
        T get(int index) {
            if (index < 0) {
                throw new IndexOutOfBoundsException();
            }

            if (index >= capacityForShift(shift)) {
                return null;
            }

            BlockTreeNode node = root;

            for (
                    int currShift = shift;
                    currShift > 0;
                    currShift -= BITS
            ) {
                int slot =
                        (index >>> currShift) & MASK;

                Object child =
                        node.children[slot];

                if (child == null) {
                    return null;
                }

                node = (BlockTreeNode) child;
            }

            int leafSlot = index & MASK;

            return (T) node.children[leafSlot];
        }

        PersistentBlockTree<T> with(
                int index,
                T value
        ) {
            if (index < 0) {
                throw new IndexOutOfBoundsException();
            }

            BlockTreeNode newRoot = root;
            int newShift = shift;

            while (index >= capacityForShift(newShift)) {
                Object[] children = new Object[BRANCHING];
                children[0] = newRoot;
                newRoot = BlockTreeNode.fromOwnedChildren(children);
                newShift += BITS;
            }

            newRoot =
                    doAssoc(
                            newRoot,
                            newShift,
                            index,
                            value
                    );

            if (newRoot == root && newShift == shift) {
                return this;
            }

            return new PersistentBlockTree<>(
                    newRoot,
                    newShift
            );
        }

        private BlockTreeNode doAssoc(
                BlockTreeNode node,
                int currentShift,
                int index,
                T value
        ) {

            Object[] newChildren;

            int slot = (index >>> currentShift) & MASK;

            if(currentShift == 0){
                Object oldValue = node.children[slot];
                if (oldValue == value) {
                    return node;
                }

                newChildren = node.children.clone();
                newChildren[slot] = value;

                return BlockTreeNode.fromOwnedChildren(newChildren);
            }

            BlockTreeNode oldChild = (BlockTreeNode) node.children[slot];
            BlockTreeNode newChild;

            if (oldChild == null) {
                newChild = newPath(
                        currentShift - BITS,
                        index,
                        value
                );
            } else {
                newChild = doAssoc(
                        oldChild,
                        currentShift - BITS,
                        index,
                        value
                );
            }

            newChildren = node.children.clone();
            newChildren[slot] = newChild;

            return BlockTreeNode.fromOwnedChildren(newChildren);
        }

        private BlockTreeNode newPath(
                int currentShift,
                int index,
                T value
        ) {
            Object[] children = new Object[BRANCHING];

            int slot = (index >>> currentShift) & MASK;

            if (currentShift == 0) {
                children[slot] = value;
                return BlockTreeNode.fromOwnedChildren(children);
            }

            children[slot] =
                    newPath(
                            currentShift - BITS,
                            index,
                            value
                    );

            return BlockTreeNode.fromOwnedChildren(children);
        }

        private static long capacityForShift(int shift) {
            return 1L << (shift + BITS);
        }

        void forEachPresent(
                BiConsumer<Integer, T> consumer
        ) {
            Objects.requireNonNull(consumer);

            forEachPresent(
                    root,
                    shift,
                    0,
                    consumer
            );
        }

        @SuppressWarnings("unchecked")
        private void forEachPresent(
                BlockTreeNode node,
                int currentShift,
                int prefix,
                BiConsumer<Integer, T> consumer
        ){
            if (currentShift == 0) {
                for (int slot = 0; slot < BRANCHING; slot++) {

                    Object value = node.children[slot];
                    if (value == null) {
                        continue;
                    }

                    consumer.accept(
                            prefix | slot,
                            (T) value
                    );
                }

                return;
            }

            for (int slot = 0; slot < BRANCHING; slot++) {
                Object child = node.children[slot];
                if (child == null) {
                    continue;
                }

                int newPrefix = prefix | (slot << currentShift);

                forEachPresent(
                        (BlockTreeNode) child,
                        currentShift - BITS,
                        newPrefix,
                        consumer
                );
            }
        }

        boolean isEmpty() {
            return isEmpty(root, shift);
        }

        private boolean isEmpty(
                BlockTreeNode node,
                int currentShift
        ) {
            if (currentShift == 0) {
                for (Object child : node.children) {
                    if (child != null) {
                        return false;
                    }
                }
                return true;
            }

            for (Object child : node.children) {
                if (child == null) {
                    continue;
                }

                if (!isEmpty(
                        (BlockTreeNode) child,
                        currentShift - BITS
                )) {
                    return false;
                }
            }

            return true;
        }
    }

    // endregion

    // region ProductTable

    static final class ProductBlock {

        private final Product[] products;

        ProductBlock(int size) {
            this.products = new Product[size];
        }

        private ProductBlock(Product[] products) {
            this.products = products;
        }

        static ProductBlock empty(int size) {
            return new ProductBlock(new Product[size]);
        }

        static ProductBlock fromArray(Product[] products) {
            return new ProductBlock(products);
        }

        static ProductBlock single(
                int size,
                int offset,
                Product product
        ) {
            Product[] products = new Product[size];
            products[offset] = product;
            return new ProductBlock(products);
        }

        Product get(int offset) {
            return products[offset];
        }

        ProductBlock with(int offset, Product product) {
            if(products[offset] == product){
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
    static final class ProductBlockTreeNode {

        private final static int BRANCHING = 32;

        private final Object[] children;

        private ProductBlockTreeNode(Object[] children){
            this.children = children;
        }

        static ProductBlockTreeNode empty(){
            return new ProductBlockTreeNode(
                    new Object[BRANCHING]
            );
        }

        static ProductBlockTreeNode fromOwnedChildren(Object[] children){
            return new ProductBlockTreeNode(
                    children
            );
        }
    }
    static final class PersistentProductBlocks {

        private static final int BRANCHING = 32;

        private static final int BITS = 5;
        private static final int MASK = BRANCHING - 1;

        private final ProductBlockTreeNode root;
        private final int shift;

        PersistentProductBlocks() {
            this.root = ProductBlockTreeNode.empty();
            this.shift = 0;
        }

        private PersistentProductBlocks(
                ProductBlockTreeNode root,
                int shift
        ) {
            this.root = root;
            this.shift = shift;
        }

        ProductBlock get(int blockIndex) {
            if (blockIndex < 0) {
                throw new IndexOutOfBoundsException();
            }

            ProductBlockTreeNode node = root;

            for(int currShift = shift; currShift > 0; currShift -= BITS){
                int slot = (blockIndex >>> currShift) & MASK;
                Object child = node.children[slot];
                if(child == null){
                    return null;
                }
                node = (ProductBlockTreeNode) child;
            }

            int leafSlot = blockIndex & MASK;
            return (ProductBlock) node.children[leafSlot];
        }

        PersistentProductBlocks with(
                int blockIndex,
                ProductBlock block
        ){
            if (blockIndex < 0) {
                throw new IndexOutOfBoundsException();
            }

            ProductBlockTreeNode newRoot = root;

            int newShift = shift;

            while(blockIndex >= capacityForShift(newShift)){
                Object[] children = new Object[BRANCHING];
                children[0] = newRoot;
                newRoot = ProductBlockTreeNode.fromOwnedChildren(children);
                newShift += BITS;
            }

            newRoot = doAssoc(
                    newRoot,
                    newShift,
                    blockIndex,
                    block
            );

            return new PersistentProductBlocks(
                    newRoot,
                    newShift
            );
        }

        private ProductBlockTreeNode doAssoc(
                ProductBlockTreeNode node,
                int currentShift,
                int blockIndex,
                ProductBlock block
        ){
            Object[] newChildren = node.children.clone();
            int slot = (blockIndex >>> currentShift) & MASK;
            if(currentShift == 0){
                newChildren[slot] = block;
                return ProductBlockTreeNode.fromOwnedChildren(newChildren);
            }

            ProductBlockTreeNode oldChild = (ProductBlockTreeNode) node.children[slot];

            ProductBlockTreeNode child = oldChild == null ? ProductBlockTreeNode.empty() : oldChild;

            ProductBlockTreeNode newChild = doAssoc(
                    child,
                    currentShift - BITS,
                    blockIndex,
                    block
            );

            newChildren[slot] = newChild;

            return ProductBlockTreeNode.fromOwnedChildren(newChildren);
        }

        private static long capacityForShift(int shift) {
            if (shift + BITS >= 63) {
                return Long.MAX_VALUE;
            }
            return 1L << (shift + BITS);
        }
    }
    static final class ProductTable {

        private static final int BLOCK_SIZE = 1024;

        private final PersistentBlockTree<ProductBlock> blocks;
        private final int blockCount;

        ProductTable() {
            this.blocks = new PersistentBlockTree<>();
            this.blockCount = 0;
        }

        private ProductTable(
                PersistentBlockTree<ProductBlock> blocks,
                int blockCount
        ) {
            this.blocks = blocks;
            this.blockCount = blockCount;
        }

        static ProductTable fromOwnedBlocks(
                PersistentBlockTree<ProductBlock> blocks,
                int blockCount
        ){
            return new ProductTable(blocks, blockCount);
        }

        Product get(int docId) {

            if (docId < 0) {
                throw new IndexOutOfBoundsException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            if(blockIndex >= blockCount){
                throw new IndexOutOfBoundsException();
            }

            ProductBlock block = blocks.get(blockIndex);

            if (block == null) {
                throw new IllegalStateException(
                        "Missing block for blockIndex=" + blockIndex
                );
            }

            return block.get(offset);
        }

        ProductBlock getBlock(int blockIndex) {
            if (blockIndex < 0 || blockIndex >= blockCount) {
                throw new IndexOutOfBoundsException();
            }

            ProductBlock block = blocks.get(blockIndex);

            if (block == null) {
                throw new IllegalStateException(
                        "Missing block for blockIndex=" + blockIndex
                );
            }

            return block;
        }

        int blockCount(){
            return blockCount;
        }

        ProductTable with(int docId, Product product) {
            if(docId < 0){
                throw new IllegalArgumentException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            if(blockIndex < blockCount){
                ProductBlock oldBlock = getBlock(blockIndex);
                ProductBlock newBlock = oldBlock.with(offset, product);
                if(oldBlock == newBlock){
                    return this;
                }
                PersistentBlockTree<ProductBlock> newBlocks = blocks.with(blockIndex, newBlock);
                return new ProductTable(newBlocks, blockCount);
            } else if (blockIndex == blockCount) {
                ProductBlock newBlock = ProductBlock.single(
                        BLOCK_SIZE,
                        offset,
                        product
                );
                PersistentBlockTree<ProductBlock> newBlocks = blocks.with(blockIndex, newBlock);
                return new ProductTable(newBlocks, blockCount + 1);
            }

            throw new IllegalArgumentException("docId has a gap");
        }

        PersistentBlockTree<ProductBlock> blocks() {
            return blocks;
        }
    }
    static final class ProductTableBuilder {

        private boolean built;
        private static final int BLOCK_SIZE = 1024;
        private final ProductTable base;
        private int blockCount;

        // key = blockIndex
        // value = 这个 batch 私有的 mutable block
        private final Map<Integer, Product[]> dirtyBlocks;

        ProductTableBuilder(ProductTable base) {
            this.built = false;
            this.base = base;
            this.dirtyBlocks = new HashMap<>();
            this.blockCount = base.blockCount();
        }

        void set(int docId, Product product) {

            ensureNotBuilt();

            if (docId < 0) {
                throw new IllegalArgumentException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            Product[] mutableBlock = dirtyBlocks.get(blockIndex);
            if(mutableBlock != null){
                mutableBlock[offset] = product;
                return;
            }

            if(blockIndex < base.blockCount()){
                Product[] copy = base.getBlock(blockIndex).copyProducts();
                copy[offset] = product;
                dirtyBlocks.put(blockIndex, copy);
            } else if (blockIndex == blockCount) {
                Product[] newBlock = new Product[BLOCK_SIZE];
                newBlock[offset] = product;
                dirtyBlocks.put(blockIndex, newBlock);
                blockCount++;
            } else {
                throw new IllegalStateException();
            }
        }

        ProductTable build() {
            ensureNotBuilt();

            PersistentBlockTree<ProductBlock> newBlocks = base.blocks();

            for (Map.Entry<Integer, Product[]> entry : dirtyBlocks.entrySet()) {
                int blockIndex = entry.getKey();
                ProductBlock newBlock = ProductBlock.fromArray(entry.getValue());
                newBlocks = newBlocks.with(blockIndex, newBlock);
            }

            built = true;
            return ProductTable.fromOwnedBlocks(newBlocks, blockCount);
        }

        Product get(int docId) {
            ensureNotBuilt();

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            Product[] dirty = dirtyBlocks.get(blockIndex);

            if (dirty != null) {
                return dirty[offset];
            }

            return base.get(docId);
        }

        private void ensureNotBuilt() {
            if (built) {
                throw new IllegalStateException("Builder already built");
            }
        }
    }

    // endregion

    // region ImmutableBitmap

    enum CandidateAccuracy {
        EXACT,
        SUPERSET
    }

    record CandidateResult(
            ImmutableBitmap bitmap,
            CandidateAccuracy accuracy
    ) {}

    static final class BitBlock {

        private final BitSet bits;

        private BitBlock(BitSet bits) {
            this.bits = bits;
        }

        static BitBlock empty(int size) {
            return new BitBlock(new BitSet(size));
        }

        static BitBlock singleSet(int size, int offset) {
            BitSet bits = new BitSet(size);
            bits.set(offset);
            return new BitBlock(bits);
        }

        static BitBlock fromOwnedBits(BitSet bits) {
            return new BitBlock(bits);
        }

        BitBlock withSet(int offset) {
            if (bits.get(offset)) {
                return this;
            }
            BitSet copy = (BitSet) bits.clone();
            copy.set(offset);
            return new BitBlock(copy);
        }

        BitBlock withClear(int offset) {
            if (!bits.get(offset)) {
                return this;
            }
            BitSet copy = (BitSet) bits.clone();
            copy.clear(offset);
            return new BitBlock(copy);
        }

        boolean get(int offset) {
            return bits.get(offset);
        }

        BitSet copyBits() {
            return (BitSet) bits.clone();
        }

        BitBlock and(BitBlock other) {
            Objects.requireNonNull(other);

            BitSet result = (BitSet) this.bits.clone();
            result.and(other.bits);

            if (result.equals(this.bits)) {
                return this;
            }

            return BitBlock.fromOwnedBits(result);
        }

        BitBlock or(BitBlock other) {
            Objects.requireNonNull(other);

            if(other.isEmpty()){
                return this;
            }

            BitSet result = (BitSet) this.bits.clone();
            result.or(other.bits);

            if (result.equals(this.bits)) {
                return this;
            }

            return BitBlock.fromOwnedBits(result);
        }

        BitBlock andNot(BitBlock other) {
            Objects.requireNonNull(other);

            BitSet result = (BitSet) this.bits.clone();
            result.andNot(other.bits);

            if (result.equals(this.bits)) {
                return this;
            }

            if(result.isEmpty()){
                return null;
            }

            return BitBlock.fromOwnedBits(result);
        }

        boolean isEmpty() {
            return bits.isEmpty();
        }

        boolean isFull(int blockSize) {
            return bits.nextClearBit(0) >= blockSize;
        }

        void forEachSetBit(
                int baseDocId,
                IntConsumer consumer
        ) {
            for (
                    int offset = bits.nextSetBit(0);
                    offset >= 0;
                    offset = bits.nextSetBit(offset + 1)
            ) {
                consumer.accept(
                        baseDocId + offset
                );
            }
        }

        int cardinality() {
            return bits.cardinality();
        }
    }
    static final class BitBlockTreeNode {

        private static final int BRANCHING = 32;

        private final Object[] children;

        private BitBlockTreeNode(Object[] children) {
            this.children = children;
        }

        static BitBlockTreeNode empty() {
            return new BitBlockTreeNode(
                    new Object[BRANCHING]
            );
        }

        static BitBlockTreeNode fromOwnedChildren(
                Object[] children
        ) {
            return new BitBlockTreeNode(children);
        }
    }
    static final class PersistentBitBlocks {

        private static final int BRANCHING = 32;
        private static final int BITS = 5;
        private static final int MASK = BRANCHING - 1;

        private final BitBlockTreeNode root;
        private final int shift;

        PersistentBitBlocks() {
            this.root = BitBlockTreeNode.empty();
            this.shift = 0;
        }

        private PersistentBitBlocks(
                BitBlockTreeNode root,
                int shift
        ) {
            this.root = root;
            this.shift = shift;
        }

        BitBlock get(int blockIndex) {
            if (blockIndex < 0) {
                throw new IndexOutOfBoundsException();
            }

            BitBlockTreeNode node = root;

            for (
                    int currShift = shift;
                    currShift > 0;
                    currShift -= BITS
            ) {
                int slot =
                        (blockIndex >>> currShift) & MASK;

                Object child =
                        node.children[slot];

                if (child == null) {
                    return null;
                }

                node = (BitBlockTreeNode) child;
            }

            int leafSlot =
                    blockIndex & MASK;

            return (BitBlock)
                    node.children[leafSlot];
        }

        PersistentBitBlocks with(
                int blockIndex,
                BitBlock block
        ) {
            if (blockIndex < 0) {
                throw new IndexOutOfBoundsException();
            }

            BitBlockTreeNode newRoot = root;
            int newShift = shift;

            while (
                    blockIndex >= capacityForShift(newShift)
            ) {
                Object[] children =
                        new Object[BRANCHING];

                children[0] = newRoot;

                newRoot =
                        BitBlockTreeNode
                                .fromOwnedChildren(children);

                newShift += BITS;
            }

            newRoot = doAssoc(
                    newRoot,
                    newShift,
                    blockIndex,
                    block
            );

            return new PersistentBitBlocks(
                    newRoot,
                    newShift
            );
        }

        private BitBlockTreeNode doAssoc(
                BitBlockTreeNode node,
                int currentShift,
                int blockIndex,
                BitBlock block
        ) {
            Object[] newChildren =
                    node.children.clone();

            int slot =
                    (blockIndex >>> currentShift) & MASK;

            if (currentShift == 0) {
                newChildren[slot] = block;

                return BitBlockTreeNode
                        .fromOwnedChildren(newChildren);
            }

            BitBlockTreeNode oldChild =
                    (BitBlockTreeNode)
                            node.children[slot];

            BitBlockTreeNode child =
                    oldChild == null
                            ? BitBlockTreeNode.empty()
                            : oldChild;

            BitBlockTreeNode newChild =
                    doAssoc(
                            child,
                            currentShift - BITS,
                            blockIndex,
                            block
                    );

            newChildren[slot] = newChild;

            return BitBlockTreeNode
                    .fromOwnedChildren(newChildren);
        }

        private static long capacityForShift(int shift) {
            return 1L << (shift + BITS);
        }
    }
    static final class ImmutableBitmap {

        private static final int BLOCK_SIZE = 1024;

        private static final int BRANCHING = 32;
        private static final int BITS = 5;
        private static final int MASK = BRANCHING - 1;

        private final PersistentBlockTree<BitBlock> blocks;
        private final int blockCount;
        private final int cardinality;

        ImmutableBitmap() {
            this.blocks = new PersistentBlockTree<>();
            this.blockCount = 0;
            this.cardinality = 0;
        }

        private ImmutableBitmap(
                PersistentBlockTree<BitBlock> blocks,
                int blockCount,
                int cardinality
        ) {
            this.blocks = blocks;
            this.blockCount = blockCount;
            this.cardinality = cardinality;
        }

        static ImmutableBitmap empty(){
            return new ImmutableBitmap();
        }

        static ImmutableBitmap fromOwnedBlocks(
                PersistentBlockTree<BitBlock> blocks,
                int blockCount,
                int cardinality
        ) {
            return new ImmutableBitmap(blocks, blockCount, cardinality);
        }

        boolean get(int docId) {

            if (docId < 0) {
                return false;
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            if (blockIndex >= blockCount) {
                return false;
            }

            BitBlock block = blocks.get(blockIndex);

            return block != null && block.get(offset);
        }

        ImmutableBitmap withSet(int docId) {
            if (docId < 0) {
                throw new IllegalArgumentException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            BitBlock oldBlock = getBlockOrNull(blockIndex);
            BitBlock newBlock;
            if(oldBlock == null){
                newBlock = BitBlock.singleSet(
                        BLOCK_SIZE,
                        offset
                );
            }else{
                newBlock = oldBlock.withSet(offset);
                if(oldBlock == newBlock){
                    return this;
                }
            }

            PersistentBlockTree<BitBlock> newBlocks =
                    blocks.with(
                            blockIndex,
                            newBlock
                    );

            int newBlockCount =
                    Math.max(
                            blockCount,
                            blockIndex + 1
                    );

            return new ImmutableBitmap(
                    newBlocks,
                    newBlockCount,
                    cardinality + 1
            );
        }

        ImmutableBitmap withClear(int docId) {
            if (docId < 0) {
                throw new IllegalArgumentException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            if (blockIndex >= blockCount) {
                return this;
            }

            BitBlock oldBlock = getBlockOrNull(blockIndex);
            if(oldBlock == null){
                return this;
            }

            BitBlock newBlock = oldBlock.withClear(offset);

            if (oldBlock == newBlock) {
                return this;
            }

            BitBlock replacement =
                    newBlock.isEmpty()
                            ? null
                            : newBlock;

            PersistentBlockTree<BitBlock> newBlocks =
                    blocks.with(
                            blockIndex,
                            replacement
                    );

            return new ImmutableBitmap(
                    newBlocks,
                    blockCount,
                    cardinality - 1
            );
        }

        BitBlock getBlockOrNull(int blockIndex) {
            if (blockIndex < 0 || blockIndex >= blockCount) {
                return null;
            }

            return blocks.get(blockIndex);
        }

        PersistentBlockTree<BitBlock> blocks() {
            return blocks;
        }

        int blockCount() {
            return blockCount;
        }

        boolean isEmpty(){
            return blocks.isEmpty();
        }

        ImmutableBitmap and(ImmutableBitmap other) {
            Objects.requireNonNull(other);

            if (this.blockCount == 0 || other.blockCount == 0) {
                return new ImmutableBitmap();
            }

            int resultShift =
                    Math.min(
                            this.blocks.shift(),
                            other.blocks.shift()
                    );

            PersistentBlockTree<BitBlock> resultBlocks =
                    new PersistentBlockTree<>();

            BlockTreeNode newRoot =
                    andNodes(
                            this.blocks.root(),
                            this.blocks.shift(),
                            other.blocks.root(),
                            other.blocks.shift()
                    );

            if (newRoot == null) {
                return new ImmutableBitmap();
            }

            if (
                    resultShift == this.blocks.shift()
                            && newRoot == this.blocks.root()
            ) {
                return this;
            }

            PersistentBlockTree<BitBlock> newBlocks =
                    PersistentBlockTree.fromOwnedRoot(
                            newRoot,
                            resultShift
                    );

            int resultBlockCount =
                    Math.min(
                            this.blockCount,
                            other.blockCount
                    );

            int newCardinality =
                    computeCardinality(newBlocks);

            return ImmutableBitmap.fromOwnedBlocks(
                    newBlocks,
                    resultBlockCount,
                    newCardinality
            );
        }

        private BlockTreeNode andNodes(
                BlockTreeNode a,
                int aShift,
                BlockTreeNode b,
                int bShift
        ){
            if(a == null || b == null){
                return null;
            }

            if(aShift < bShift){
                return andNodes(
                        b,
                        bShift,
                        a,
                        aShift
                );
            }

            if(aShift > bShift){

                BlockTreeNode aChild = (BlockTreeNode) a.children[0];

                if(aChild == null){
                    return null;
                }

                return andNodes(
                        aChild,
                        aShift - BITS,
                        b,
                        bShift
                );
            }

            // aShift == bShift

            if (aShift > 0) {
                Object[] newChildren = null;

                for (int slot = 0; slot < BRANCHING; slot++) {

                    BlockTreeNode aChild = (BlockTreeNode) a.children[slot];

                    if (aChild == null) {
                        continue;
                    }

                    BlockTreeNode bChild = (BlockTreeNode) b.children[slot];

                    BlockTreeNode merged =
                            bChild == null
                                    ? null
                                    : andNodes(
                                    aChild,
                                    aShift - BITS,
                                    bChild,
                                    bShift - BITS
                            );

                    if (merged != aChild) {
                        if (newChildren == null) {
                            newChildren = a.children.clone();
                        }

                        newChildren[slot] = merged;
                    }
                }

                if (newChildren == null) {
                    return a;
                }

                return BlockTreeNode.fromOwnedChildren(
                        newChildren
                );
            }

            // aShift == bShift == 0

            Object[] newChildren = null;

            for (int slot = 0; slot < BRANCHING; slot++) {

                BitBlock aBlock = (BitBlock) a.children[slot];

                if (aBlock == null) {
                    continue;
                }

                BitBlock bBlock = (BitBlock) b.children[slot];

                BitBlock resultBlock;

                if (bBlock == null) {
                    resultBlock = null;
                } else {
                    resultBlock = aBlock.and(bBlock);

                    if (resultBlock.isEmpty()) {
                        resultBlock = null;
                    }
                }

                if (resultBlock != aBlock) {
                    if (newChildren == null) {
                        newChildren = a.children.clone();
                    }
                    newChildren[slot] = resultBlock;
                }
            }

            if (newChildren == null) {
                return a;
            }

            return BlockTreeNode.fromOwnedChildren(
                    newChildren
            );

        }

        ImmutableBitmap or(ImmutableBitmap other) {
            Objects.requireNonNull(other);

            if (this.blockCount == 0) {
                return other;
            }

            if (other.blockCount == 0) {
                return this;
            }

            int resultShift =
                    Math.max(
                            this.blocks.shift(),
                            other.blocks.shift()
                    );

            BlockTreeNode newRoot =
                    orNodes(
                            this.blocks.root(),
                            this.blocks.shift(),
                            other.blocks.root(),
                            other.blocks.shift()
                    );

            if (
                    resultShift == this.blocks.shift()
                            && newRoot == this.blocks.root()
            ) {
                return this;
            }

            if (
                    resultShift == other.blocks.shift()
                            && newRoot == other.blocks.root()
            ) {
                return other;
            }

            PersistentBlockTree<BitBlock> newBlocks =
                    PersistentBlockTree.fromOwnedRoot(
                            newRoot,
                            resultShift
                    );

            int resultBlockCount =
                    Math.max(
                            this.blockCount,
                            other.blockCount
                    );

            int newCardinality =
                    computeCardinality(newBlocks);

            return ImmutableBitmap.fromOwnedBlocks(
                    newBlocks,
                    resultBlockCount,
                    newCardinality
            );
        }

        private BlockTreeNode orNodes(
                BlockTreeNode a,
                int aShift,
                BlockTreeNode b,
                int bShift
        ) {
            if (a == null) {
                return b;
            }

            if (b == null) {
                return a;
            }

            if (aShift < bShift) {
                return orNodes(
                        b,
                        bShift,
                        a,
                        aShift
                );
            }

            if (aShift > bShift) {
                BlockTreeNode aChild = (BlockTreeNode) a.children[0];

                BlockTreeNode merged =
                        orNodes(
                                aChild,
                                aShift - BITS,
                                b,
                                bShift
                        );

                if (merged == aChild) {
                    return a;
                }

                Object[] newChildren = a.children.clone();
                newChildren[0] = merged;

                return BlockTreeNode.fromOwnedChildren(
                        newChildren
                );
            }

            // aShift == bShift

            if (aShift > 0) {
                Object[] newChildren = null;

                for (int slot = 0; slot < BRANCHING; slot++) {

                    BlockTreeNode aChild = (BlockTreeNode) a.children[slot];

                    BlockTreeNode bChild = (BlockTreeNode) b.children[slot];

                    BlockTreeNode merged;

                    if (aChild == null) {
                        merged = bChild;
                    } else if (bChild == null) {
                        merged = aChild;
                    } else {
                        merged = orNodes(
                                aChild,
                                aShift - BITS,
                                bChild,
                                bShift - BITS
                        );
                    }

                    if (merged != aChild) {
                        if (newChildren == null) {
                            newChildren = a.children.clone();
                        }
                        newChildren[slot] = merged;
                    }
                }

                if (newChildren == null) {
                    return a;
                }

                return BlockTreeNode.fromOwnedChildren(
                        newChildren
                );
            }

            // leaf level
            Object[] newChildren = null;

            for (int slot = 0; slot < BRANCHING; slot++) {

                BitBlock aBlock = (BitBlock) a.children[slot];

                BitBlock bBlock = (BitBlock) b.children[slot];

                BitBlock resultBlock;

                if (aBlock == null) {
                    resultBlock = bBlock;
                } else if (bBlock == null) {
                    resultBlock = aBlock;
                } else {
                    resultBlock = aBlock.or(bBlock);
                }

                if (resultBlock != aBlock) {
                    if (newChildren == null) {
                        newChildren = a.children.clone();
                    }
                    newChildren[slot] = resultBlock;
                }
            }

            if (newChildren == null) {
                return a;
            }

            return BlockTreeNode.fromOwnedChildren(
                    newChildren
            );
        }

        ImmutableBitmap andNot(ImmutableBitmap other) {
            Objects.requireNonNull(other);

            if (this.blockCount == 0 || other.blockCount == 0) {
                return this;
            }

            BlockTreeNode newRoot = andNotNodes(
                    this.blocks.root(),
                    this.blocks.shift(),
                    other.blocks.root(),
                    other.blocks.shift()
            );

            if (newRoot == this.blocks.root()) {
                return this;
            }

            PersistentBlockTree<BitBlock> newBlocks =
                    PersistentBlockTree.fromOwnedRoot(
                            newRoot,
                            this.blocks.shift()
                    );

            int newCardinality =
                    computeCardinality(newBlocks);

            return ImmutableBitmap.fromOwnedBlocks(
                    newBlocks,
                    this.blockCount,
                    newCardinality
            );
        }

        private BlockTreeNode andNotNodes(
                BlockTreeNode a,
                int aShift,
                BlockTreeNode b,
                int bShift
        ){
            if(a == null){
                return null;
            }
            if(b == null){
                return a;
            }

            if(aShift > bShift){
                BlockTreeNode aChild = (BlockTreeNode) a.children[0];
                BlockTreeNode merged = andNotNodes(
                        aChild,
                        aShift - BITS,
                        b,
                        bShift
                );
                if(merged == aChild){
                    return a;
                }
                Object[] newChildren = a.children.clone();
                newChildren[0] = merged;
                return BlockTreeNode.fromOwnedChildren(newChildren);
            }

            if (aShift < bShift) {
                BlockTreeNode bChild = (BlockTreeNode) b.children[0];
                if (bChild == null) {
                    return a;
                }

                return andNotNodes(
                        a,
                        aShift,
                        bChild,
                        bShift - BITS
                );
            }

            // aShift == bShift

            if(aShift > 0){
                Object[] newChildren = null;
                for (int slot = 0; slot < BRANCHING; slot++) {

                    BlockTreeNode aChild = (BlockTreeNode) a.children[slot];
                    if (aChild == null) {
                        continue;
                    }

                    BlockTreeNode bChild = (BlockTreeNode) b.children[slot];
                    if (bChild == null) {
                        continue;
                    }

                    BlockTreeNode merged = andNotNodes(
                            aChild,
                            aShift - BITS,
                            bChild,
                            bShift - BITS
                    );

                    if (merged != aChild) {
                        if (newChildren == null) {
                            newChildren = a.children.clone();
                        }
                        newChildren[slot] = merged;
                    }
                }

                if (newChildren == null) {
                    return a;
                }

                return BlockTreeNode.fromOwnedChildren(
                        newChildren
                );
            }

            // leaf level

            Object[] newChildren = null;

            for (int slot = 0; slot < BRANCHING; slot++) {

                BitBlock aBlock = (BitBlock) a.children[slot];

                if (aBlock == null) {
                    continue;
                }

                BitBlock bBlock = (BitBlock) b.children[slot];
                if (bBlock == null) {
                    continue;
                }

                BitBlock resultBlock = aBlock.andNot(bBlock);

                if (resultBlock != aBlock) {
                    if (newChildren == null) {
                        newChildren = a.children.clone();
                    }
                    newChildren[slot] = resultBlock;
                }
            }

            if (newChildren == null) {
                return a;
            }

            return BlockTreeNode.fromOwnedChildren(
                    newChildren
            );
        }

        void forEachSetBit(IntConsumer consumer) {
            Objects.requireNonNull(consumer);

            blocks.forEachPresent(
                    (blockIndex, block) -> {
                        int baseDocId = blockIndex * BLOCK_SIZE;

                        block.forEachSetBit(
                                baseDocId,
                                consumer
                        );
                    }
            );
        }

        int cardinality() {
            final int[] count = {0};

            blocks.forEachPresent(
                    (blockIndex, block) ->
                            count[0] += block.cardinality()
            );

            return count[0];
        }

        private static int computeCardinality(
                PersistentBlockTree<BitBlock> blocks
        ) {
            int[] count = {0};

            blocks.forEachPresent(
                    (index, block) ->
                            count[0] += block.cardinality()
            );

            return count[0];
        }
    }
    static final class ImmutableBitmapBuilder {

        private static final int BLOCK_SIZE = 1024;

        private final ImmutableBitmap base;

        // 当前 batch 已经 copy / 新建过的 mutable blocks
        private final Map<Integer, BitSet> dirtyBlocks;

        private int cardinality;
        private int blockCount;
        private boolean built;

        ImmutableBitmapBuilder(ImmutableBitmap base) {
            this.base = Objects.requireNonNull(base);
            this.dirtyBlocks = new HashMap<>();
            this.blockCount = base.blockCount();
            this.cardinality = base.cardinality();
            this.built = false;
        }

        boolean get(int docId) {
            ensureNotBuilt();

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            BitSet dirty = dirtyBlocks.get(blockIndex);

            if (dirty != null) {
                return dirty.get(offset);
            }

            return base.get(docId);
        }

        void set(int docId) {
            ensureNotBuilt();

            if (docId < 0) {
                throw new IllegalArgumentException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            BitSet mutableBits = dirtyBlocks.get(blockIndex);

            // 当前 batch 已经 copy 过这个 block
            if (mutableBits != null) {
                if(!mutableBits.get(offset)){
                    mutableBits.set(offset);
                    cardinality++;
                }
                return;
            }

            BitBlock oldBlock = base.getBlockOrNull(blockIndex);

            if (oldBlock != null) {

                if (oldBlock.get(offset)) {
                    return;
                }

                BitSet copy = oldBlock.copyBits();
                copy.set(offset);

                dirtyBlocks.put(
                        blockIndex,
                        copy
                );

            } else {

                BitSet newBits = new BitSet(BLOCK_SIZE);
                newBits.set(offset);

                dirtyBlocks.put(
                        blockIndex,
                        newBits
                );
            }

            blockCount =
                    Math.max(
                            blockCount,
                            blockIndex + 1
                    );

            cardinality++;
        }

        void clear(int docId) {
            ensureNotBuilt();

            if (docId < 0) {
                throw new IllegalArgumentException();
            }

            int blockIndex = docId / BLOCK_SIZE;
            int offset = docId % BLOCK_SIZE;

            if (blockIndex >= blockCount) {
                return;
            }

            BitSet mutableBits = dirtyBlocks.get(blockIndex);
            if (mutableBits != null) {
                if (mutableBits.get(offset)) {
                    mutableBits.clear(offset);
                    cardinality--;
                }
                return;
            }

            BitBlock oldBlock = base.getBlockOrNull(blockIndex);

            if (oldBlock == null || !oldBlock.get(offset)) {
                return;
            }

            BitSet copy = oldBlock.copyBits();
            copy.clear(offset);

            dirtyBlocks.put(
                    blockIndex,
                    copy
            );

            cardinality--;
        }

        ImmutableBitmap build() {
            ensureNotBuilt();

            PersistentBlockTree<BitBlock> newBlocks = base.blocks();

            for (Map.Entry<Integer, BitSet> entry : dirtyBlocks.entrySet()) {
                int blockIndex = entry.getKey();
                BitSet bits = entry.getValue();

                BitBlock replacement =
                        bits.isEmpty()
                                ? null
                                : BitBlock.fromOwnedBits(bits);

                newBlocks =
                        newBlocks.with(
                                blockIndex,
                                replacement
                        );
            }

            built = true;

            return ImmutableBitmap.fromOwnedBlocks(
                    newBlocks,
                    blockCount,
                    cardinality
            );
        }

        private void ensureNotBuilt() {
            if (built) {
                throw new IllegalStateException("Builder already built");
            }
        }
    }

    // endregion

    // region snapshot

    static final class CategoryIndexSnapshot {

        private final EnumMap<Category, ImmutableBitmap> index;

        CategoryIndexSnapshot() {
            this.index = new EnumMap<>(Category.class);
        }

        private CategoryIndexSnapshot(
                EnumMap<Category, ImmutableBitmap> index
        ) {
            this.index = index;
        }

        ImmutableBitmap get(Category category) {
            ImmutableBitmap bitmap = index.get(category);

            return bitmap == null
                    ? new ImmutableBitmap()
                    : bitmap;
        }

        CategoryIndexSnapshot withAdd(
                Category category,
                int docId
        ) {
            EnumMap<Category, ImmutableBitmap> copy = new EnumMap<>(index);

            ImmutableBitmap oldBitmap = copy.get(category);

            if (oldBitmap == null) {
                oldBitmap = new ImmutableBitmap();
            }

            ImmutableBitmap newBitmap = oldBitmap.withSet(docId);

            if (newBitmap == oldBitmap) {
                return this;
            }

            copy.put(category, newBitmap);

            return new CategoryIndexSnapshot(copy);
        }

        CategoryIndexSnapshot withRemove(
                Category category,
                int docId
        ) {
            ImmutableBitmap oldBitmap = index.get(category);

            if (oldBitmap == null) {
                return this;
            }

            ImmutableBitmap newBitmap = oldBitmap.withClear(docId);

            if (newBitmap == oldBitmap) {
                return this;
            }

            EnumMap<Category, ImmutableBitmap> copy = new EnumMap<>(index);

            if (newBitmap.isEmpty()) {
                copy.remove(category);
            } else {
                copy.put(category, newBitmap);
            }

            return new CategoryIndexSnapshot(copy);
        }

        CategoryIndexSnapshot withUpdate(
                Category oldCategory,
                Category newCategory,
                int docId
        ) {
            if (oldCategory == newCategory) {
                return this;
            }

            CategoryIndexSnapshot result =
                    withRemove(oldCategory, docId);

            return result.withAdd(
                    newCategory,
                    docId
            );
        }

        EnumMap<Category, ImmutableBitmap> copyIndex() {
            return new EnumMap<>(index);
        }

        static CategoryIndexSnapshot fromOwnedIndex(
                EnumMap<Category, ImmutableBitmap> index
        ) {
            return new CategoryIndexSnapshot(index);
        }
    }
    static final class CategoryIndexBuilder {

        private final CategoryIndexSnapshot base;
        private final EnumMap<Category, ImmutableBitmapBuilder> dirty;
        private boolean built;

        CategoryIndexBuilder(CategoryIndexSnapshot base) {
            this.base = Objects.requireNonNull(base);
            this.dirty = new EnumMap<>(Category.class);
            this.built = false;
        }

        private ImmutableBitmapBuilder builderFor(
                Category category
        ) {
            return dirty.computeIfAbsent(
                    category,
                    c -> new ImmutableBitmapBuilder(
                            base.get(c)
                    )
            );
        }

        void add(Category category, int docId) {
            ensureNotBuilt();
            builderFor(category).set(docId);
        }

        void remove(Category category, int docId) {
            ensureNotBuilt();
            builderFor(category).clear(docId);
        }

        void update(
                Category oldCategory,
                Category newCategory,
                int docId
        ) {
            ensureNotBuilt();

            if (oldCategory == newCategory) {
                return;
            }

            remove(oldCategory, docId);
            add(newCategory, docId);
        }

        CategoryIndexSnapshot build() {
            ensureNotBuilt();

            EnumMap<Category, ImmutableBitmap> newIndex = base.copyIndex();

            for (
                    Map.Entry<Category, ImmutableBitmapBuilder> entry
                    : dirty.entrySet()
            ) {
                Category category = entry.getKey();
                ImmutableBitmap newBitmap = entry.getValue().build();
                if (newBitmap.isEmpty()) {
                    newIndex.remove(category);
                } else {
                    newIndex.put(category, newBitmap);
                }
            }

            built = true;
            return CategoryIndexSnapshot.fromOwnedIndex(newIndex);
        }

        private void ensureNotBuilt() {
            if (built) {
                throw new IllegalStateException("Builder already built");
            }
        }
    }

    static final class PrimeIndexSnapshot {

        private final ImmutableBitmap primeProducts;

        PrimeIndexSnapshot() {
            this.primeProducts = new ImmutableBitmap();
        }

        private PrimeIndexSnapshot(
                ImmutableBitmap primeProducts
        ) {
            this.primeProducts = primeProducts;
        }

        ImmutableBitmap primeProducts() {
            return primeProducts;
        }

        PrimeIndexSnapshot withAdd(
                Product product,
                int docId
        ) {
            if (!product.prime()) {
                return this;
            }

            ImmutableBitmap newBitmap = primeProducts.withSet(docId);

            if (newBitmap == primeProducts) {
                return this;
            }

            return new PrimeIndexSnapshot(newBitmap);
        }

        PrimeIndexSnapshot withRemove(
                Product product,
                int docId
        ) {
            if (!product.prime()) {
                return this;
            }

            ImmutableBitmap newBitmap = primeProducts.withClear(docId);

            if (newBitmap == primeProducts) {
                return this;
            }

            return new PrimeIndexSnapshot(newBitmap);
        }

        PrimeIndexSnapshot withUpdate(
                boolean oldPrime,
                boolean newPrime,
                int docId
        ) {
            if (oldPrime == newPrime) {
                return this;
            }

            ImmutableBitmap newBitmap =
                    newPrime
                            ? primeProducts.withSet(docId)
                            : primeProducts.withClear(docId);

            if (newBitmap == primeProducts) {
                return this;
            }

            return new PrimeIndexSnapshot(newBitmap);
        }

        static PrimeIndexSnapshot fromOwnedBitmap(
                ImmutableBitmap bitmap
        ) {
            return new PrimeIndexSnapshot(bitmap);
        }
    }
    static final class PrimeIndexBuilder {

        private final ImmutableBitmapBuilder primeProductsBuilder;

        private boolean built;

        PrimeIndexBuilder(PrimeIndexSnapshot base) {
            this.primeProductsBuilder =
                    new ImmutableBitmapBuilder(
                            base.primeProducts()
                    );

            this.built = false;
        }

        void add(Product product, int docId) {
            ensureNotBuilt();

            if (product.prime()) {
                primeProductsBuilder.set(docId);
            }
        }

        void remove(Product product, int docId) {
            ensureNotBuilt();

            if (product.prime()) {
                primeProductsBuilder.clear(docId);
            }
        }

        void update(
                Product oldProduct,
                Product newProduct,
                int docId
        ) {
            ensureNotBuilt();

            if (oldProduct.prime() == newProduct.prime()) {
                return;
            }

            if (newProduct.prime()) {
                primeProductsBuilder.set(docId);
            } else {
                primeProductsBuilder.clear(docId);
            }
        }

        PrimeIndexSnapshot build() {
            ensureNotBuilt();

            ImmutableBitmap primeProducts = primeProductsBuilder.build();

            built = true;

            return PrimeIndexSnapshot.fromOwnedBitmap(
                    primeProducts
            );
        }

        private void ensureNotBuilt() {
            if (built) {
                throw new IllegalStateException("Builder already built");
            }
        }
    }

    static final class PriceIndexSnapshot {

        private final NavigableMap<Double, ImmutableBitmap> index;

        PriceIndexSnapshot() {
            this.index = Collections.unmodifiableNavigableMap(
                    new TreeMap<>()
            );
        }

        private PriceIndexSnapshot(
                NavigableMap<Double, ImmutableBitmap> index
        ) {
            this.index = Collections.unmodifiableNavigableMap(
                    index
            );
        }

        ImmutableBitmap get(double price) {
            ImmutableBitmap bitmap =
                    index.get(price);

            return bitmap == null
                    ? ImmutableBitmap.empty()
                    : bitmap;
        }

        ImmutableBitmap getByRange(
                double minPrice,
                double maxPrice
        ) {
            if (Double.compare(minPrice, maxPrice) > 0) {
                return ImmutableBitmap.empty();
            }

            NavigableMap<Double, ImmutableBitmap> range =
                    index.subMap(
                            minPrice,
                            true,
                            maxPrice,
                            true
                    );

            ImmutableBitmap result =
                    ImmutableBitmap.empty();

            for (ImmutableBitmap bitmap : range.values()) {
                result = result.or(bitmap);
            }

            return result;
        }

        PriceIndexSnapshot withAdd(
                double price,
                int docId
        ) {
            ImmutableBitmap oldBitmap =
                    index.get(price);

            if (oldBitmap == null) {
                oldBitmap = ImmutableBitmap.empty();
            }

            ImmutableBitmap newBitmap =
                    oldBitmap.withSet(docId);

            if (newBitmap == oldBitmap) {
                return this;
            }

            TreeMap<Double, ImmutableBitmap> copy =
                    new TreeMap<>(index);

            copy.put(price, newBitmap);

            return new PriceIndexSnapshot(copy);
        }

        PriceIndexSnapshot withRemove(
                double price,
                int docId
        ) {
            ImmutableBitmap oldBitmap =
                    index.get(price);

            if (oldBitmap == null) {
                return this;
            }

            ImmutableBitmap newBitmap =
                    oldBitmap.withClear(docId);

            if (newBitmap == oldBitmap) {
                return this;
            }

            TreeMap<Double, ImmutableBitmap> copy =
                    new TreeMap<>(index);

            if (newBitmap.isEmpty()) {
                copy.remove(price);
            } else {
                copy.put(price, newBitmap);
            }

            return new PriceIndexSnapshot(copy);
        }

        PriceIndexSnapshot withUpdate(
                double oldPrice,
                double newPrice,
                int docId
        ) {
            if (Double.compare(oldPrice, newPrice) == 0) {
                return this;
            }

            return withRemove(oldPrice, docId)
                    .withAdd(newPrice, docId);
        }

        TreeMap<Double, ImmutableBitmap> copyIndex() {
            return new TreeMap<>(index);
        }

        static PriceIndexSnapshot fromOwnedIndex(
                TreeMap<Double, ImmutableBitmap> index
        ) {
            return new PriceIndexSnapshot(index);
        }
    }
    static final class PriceIndexBuilder {

        private final PriceIndexSnapshot base;

        private final Map<Double, ImmutableBitmapBuilder> dirty;

        private boolean built;

        PriceIndexBuilder(
                PriceIndexSnapshot base
        ) {
            this.base = Objects.requireNonNull(base);
            this.dirty = new HashMap<>();
            this.built = false;
        }

        private ImmutableBitmapBuilder builderFor(
                double price
        ) {
            return dirty.computeIfAbsent(
                    price,
                    p -> new ImmutableBitmapBuilder(
                            base.get(p)
                    )
            );
        }

        void add(
                double price,
                int docId
        ) {
            ensureNotBuilt();

            builderFor(price).set(docId);
        }

        void remove(
                double price,
                int docId
        ) {
            ensureNotBuilt();

            builderFor(price).clear(docId);
        }

        void update(
                double oldPrice,
                double newPrice,
                int docId
        ) {
            ensureNotBuilt();

            if (Double.compare(
                    oldPrice,
                    newPrice
            ) == 0) {
                return;
            }

            remove(oldPrice, docId);
            add(newPrice, docId);
        }

        // build
        PriceIndexSnapshot build() {
            ensureNotBuilt();

            TreeMap<Double, ImmutableBitmap> newIndex =
                    base.copyIndex();

            for (
                    Map.Entry<Double, ImmutableBitmapBuilder> entry
                    : dirty.entrySet()
            ) {
                double price =
                        entry.getKey();

                ImmutableBitmap newBitmap =
                        entry.getValue().build();

                if (newBitmap.isEmpty()) {
                    newIndex.remove(price);
                } else {
                    newIndex.put(
                            price,
                            newBitmap
                    );
                }
            }

            built = true;

            return PriceIndexSnapshot.fromOwnedIndex(
                    newIndex
            );
        }

        private void ensureNotBuilt() {
            if (built) {
                throw new IllegalStateException("Builder already built");
            }
        }
    }

    static final class CatalogSnapshot {
        private final ProductTable productTable;
        private final ImmutableBitmap activeProducts;
        private final CategoryIndexSnapshot categoryIndex;
        private final PrimeIndexSnapshot primeIndex;
        private final PriceIndexSnapshot priceIndex;

        CatalogSnapshot() {
            this.productTable = new ProductTable();
            this.activeProducts = new ImmutableBitmap();
            this.categoryIndex = new CategoryIndexSnapshot();
            this.primeIndex = new PrimeIndexSnapshot();
            this.priceIndex = new PriceIndexSnapshot();
        }

        private CatalogSnapshot(
                ProductTable productTable,
                ImmutableBitmap activeProducts,
                CategoryIndexSnapshot categoryIndex,
                PrimeIndexSnapshot primeIndex,
                PriceIndexSnapshot priceIndex
        ) {
            this.productTable = productTable;
            this.activeProducts = activeProducts;
            this.categoryIndex = categoryIndex;
            this.primeIndex = primeIndex;
            this.priceIndex = priceIndex;
        }

        static CatalogSnapshot fromOwnedComponents(
                ProductTable productTable,
                ImmutableBitmap activeProducts,
                CategoryIndexSnapshot categoryIndex,
                PrimeIndexSnapshot primeIndex,
                PriceIndexSnapshot priceIndex
        ) {
            return new CatalogSnapshot(
                    productTable,
                    activeProducts,
                    categoryIndex,
                    primeIndex,
                    priceIndex
            );
        }

        ProductTable productTable() {
            return productTable;
        }

        ImmutableBitmap activeProducts() {
            return activeProducts;
        }

        CategoryIndexSnapshot categoryIndex() {
            return categoryIndex;
        }

        PrimeIndexSnapshot primeIndex() {
            return primeIndex;
        }

        PriceIndexSnapshot priceIndex() {
            return priceIndex;
        }

        Product get(int docId) {
            if (!activeProducts.get(docId)) {
                return null;
            }

            return productTable.get(docId);
        }

        CatalogSnapshot add(
                int docId,
                Product product
        ) {
            if (activeProducts.get(docId)) {
                throw new IllegalStateException();
            }
            return new CatalogSnapshot(
                    productTable.with(docId, product),
                    activeProducts.withSet(docId),
                    categoryIndex.withAdd(product.category(), docId),
                    primeIndex.withAdd(product, docId),
                    priceIndex.withAdd(product.price(), docId)
            );
        }

        CatalogSnapshot remove(int docId) {
            if (!activeProducts.get(docId)) {
                return this;
            }

            Product product = productTable.get(docId);

            return new CatalogSnapshot(
                    productTable.with(docId, null),
                    activeProducts.withClear(docId),
                    categoryIndex.withRemove(product.category(), docId),
                    primeIndex.withRemove(product, docId),
                    priceIndex.withRemove(product.price(), docId)
            );
        }

        CatalogSnapshot update(
                int docId,
                Product product
        ) {
            if (!activeProducts.get(docId)) {
                throw new IllegalStateException();
            }
            Product oldProduct = productTable.get(docId);
            if (oldProduct == null) {
                throw new IllegalStateException(
                        "Active docId has no product"
                );
            }

            if (oldProduct == product) {
                return this;
            }

            return new CatalogSnapshot(
                    productTable.with(docId, product),
                    activeProducts,
                    categoryIndex.withUpdate(
                            oldProduct.category(),
                            product.category(),
                            docId
                    ),
                    primeIndex.withUpdate(
                            oldProduct.prime(),
                            product.prime(),
                            docId
                    ),
                    priceIndex.withAdd(
                            product.price(),
                            docId
                    )
            );
        }

        ImmutableBitmap getPrimeCandidates(boolean requirePrime) {
            if (requirePrime) {
                return primeIndex.primeProducts();
            }

            return activeProducts.andNot(
                    primeIndex.primeProducts()
            );
        }

        Optional<CandidateResult> getCandidates(
                ProductFilter filter
        ) {
            Objects.requireNonNull(filter);
            switch (filter) {
                case AndFilter andFilter -> {

                    List<ImmutableBitmap> indexedCandidates = new ArrayList<>();

                    CandidateAccuracy accuracy = CandidateAccuracy.EXACT;

                    for (ProductFilter child : andFilter.filters()) {
                        Optional<CandidateResult> childOpt = getCandidates(child);
                        if (childOpt.isEmpty()) {
                            accuracy = CandidateAccuracy.SUPERSET;
                            continue;
                        }
                        CandidateResult childResult = childOpt.get();
                        ImmutableBitmap childCandidates = childResult.bitmap();
                        if (childCandidates.isEmpty()) {
                            return Optional.of(
                                    new CandidateResult(
                                            childResult.bitmap(),
                                            CandidateAccuracy.EXACT
                                    )
                            );
                        }
                        CandidateAccuracy childAccuracy = childResult.accuracy();
                        if(childAccuracy == CandidateAccuracy.SUPERSET){
                            accuracy = CandidateAccuracy.SUPERSET;
                        }
                        indexedCandidates.add(childCandidates);
                    }

                    if (indexedCandidates.isEmpty()) {
                        return Optional.empty();
                    }

                    indexedCandidates.sort(
                            Comparator.comparingInt(
                                    ImmutableBitmap::cardinality
                            )
                    );

                    ImmutableBitmap candidates = indexedCandidates.getFirst();

                    for (int i = 1; i < indexedCandidates.size(); i++) {

                        candidates =
                                candidates.and(
                                        indexedCandidates.get(i)
                                );

                        if (candidates.isEmpty()) {
                            return Optional.of(
                                    new CandidateResult(
                                            candidates,
                                            CandidateAccuracy.EXACT
                                    )
                            );
                        }
                    }

                    return Optional.of(
                            new CandidateResult(
                                    candidates,
                                    accuracy
                            )
                    );
                }
                case OrFilter orFilter -> {
                    List<ProductFilter> filters = orFilter.filters();

                    if (filters.isEmpty()) {
                        return Optional.of(
                                new CandidateResult(
                                        ImmutableBitmap.empty(),
                                        CandidateAccuracy.EXACT
                                )
                        );
                    }

                    ImmutableBitmap candidates = null;

                    CandidateAccuracy accuracy = CandidateAccuracy.EXACT;

                    for (ProductFilter child : filters) {

                        Optional<CandidateResult> childOpt = getCandidates(child);

                        if (childOpt.isEmpty()) {
                            return Optional.empty();
                        }

                        ImmutableBitmap childCandidates = childOpt.get().bitmap();
                        CandidateAccuracy childAccuracy = childOpt.get().accuracy();
                        if(childAccuracy == CandidateAccuracy.SUPERSET){
                            accuracy = CandidateAccuracy.SUPERSET;
                        }

                        if (candidates == null) {
                            candidates = childCandidates;
                        } else {
                            candidates = candidates.or(childCandidates);
                        }
                    }

                    return Optional.of(
                            new CandidateResult(
                                    candidates,
                                    accuracy
                            )
                    );
                }
                case NotFilter notFilter -> {

                    Optional<CandidateResult> childOpt =
                            getCandidates(
                                    notFilter.filter()
                            );

                    if (childOpt.isEmpty()) {
                        return Optional.empty();
                    }

                    CandidateResult childResult = childOpt.get();

                    if (childResult.accuracy() != CandidateAccuracy.EXACT) {
                        return Optional.empty();
                    }

                    ImmutableBitmap candidates =
                            activeProducts.andNot(
                                    childResult.bitmap()
                            );

                    return Optional.of(
                            new CandidateResult(
                                    candidates,
                                    CandidateAccuracy.EXACT
                            )
                    );
                }
                case CategoryFilter categoryFilter -> {
                    return Optional.of(
                            new CandidateResult(
                                    categoryIndex.get(
                                            categoryFilter.category()
                                    ),
                                    CandidateAccuracy.EXACT
                            )
                    );
                }
                case PrimeFilter primeFilter -> {
                    return Optional.of(
                            new CandidateResult(
                                    getPrimeCandidates(
                                            primeFilter.requirePrime()
                                    ),
                                    CandidateAccuracy.EXACT
                            )
                    );
                }
                default -> {}
            }
            return Optional.empty();
        }
    }
    static final class CatalogSnapshotBuilder {

        private final CatalogSnapshot base;

        private final ProductTableBuilder productTableBuilder;
        private final ImmutableBitmapBuilder activeProductsBuilder;
        private final CategoryIndexBuilder categoryIndexBuilder;
        private final PrimeIndexBuilder primeIndexBuilder;
        private final PriceIndexBuilder priceIndexBuilder;

        private boolean built;

        CatalogSnapshotBuilder(CatalogSnapshot base) {
            this.base = Objects.requireNonNull(base);

            this.productTableBuilder =
                    new ProductTableBuilder(base.productTable());

            this.activeProductsBuilder =
                    new ImmutableBitmapBuilder(base.activeProducts());

            this.categoryIndexBuilder =
                    new CategoryIndexBuilder(base.categoryIndex());

            this.primeIndexBuilder =
                    new PrimeIndexBuilder(base.primeIndex());

            this.priceIndexBuilder =
                    new PriceIndexBuilder(base.priceIndex());

            this.built = false;
        }

        void add(int docId, Product product) {
            ensureNotBuilt();

            if (activeProductsBuilder.get(docId)) {
                throw new IllegalStateException();
            }

            productTableBuilder.set(docId, product);
            activeProductsBuilder.set(docId);

            categoryIndexBuilder.add(
                    product.category(),
                    docId
            );

            primeIndexBuilder.add(
                    product,
                    docId
            );

            priceIndexBuilder.add(
                    product.price(),
                    docId
            );
        }

        void remove(int docId) {
            ensureNotBuilt();

            if (!activeProductsBuilder.get(docId)) {
                return;
            }

            Product oldProduct = productTableBuilder.get(docId);

            if (oldProduct == null) {
                throw new IllegalStateException(
                        "Active docId has no product"
                );
            }

            categoryIndexBuilder.remove(
                    oldProduct.category(),
                    docId
            );

            primeIndexBuilder.remove(
                    oldProduct,
                    docId
            );

            priceIndexBuilder.remove(
                    oldProduct.price(),
                    docId
            );

            productTableBuilder.set(docId, null);
            activeProductsBuilder.clear(docId);
        }

        void update(int docId, Product product) {
            ensureNotBuilt();

            if (!activeProductsBuilder.get(docId)) {
                throw new IllegalStateException();
            }

            Product oldProduct = productTableBuilder.get(docId);

            if (oldProduct == null) {
                throw new IllegalStateException(
                        "Active docId has no product"
                );
            }

            productTableBuilder.set(docId, product);

            categoryIndexBuilder.update(
                    oldProduct.category(),
                    product.category(),
                    docId
            );

            primeIndexBuilder.update(
                    oldProduct,
                    product,
                    docId
            );

            priceIndexBuilder.update(
                    oldProduct.price(),
                    product.price(),
                    docId
            );
        }

        CatalogSnapshot build() {
            ensureNotBuilt();

            ProductTable productTable = productTableBuilder.build();
            ImmutableBitmap activeProducts = activeProductsBuilder.build();
            CategoryIndexSnapshot categoryIndex = categoryIndexBuilder.build();
            PrimeIndexSnapshot primeIndex = primeIndexBuilder.build();
            PriceIndexSnapshot priceIndex = priceIndexBuilder.build();

            built = true;

            return CatalogSnapshot.fromOwnedComponents(
                    productTable,
                    activeProducts,
                    categoryIndex,
                    primeIndex,
                    priceIndex
            );
        }

        private void ensureNotBuilt() {
            if (built) {
                throw new IllegalStateException("Builder already built");
            }
        }
    }

    // endregion

    // region multiple writer thread
    static final class VersionedProductCatalog {

        private final AtomicReference<CatalogSnapshot> current;

        VersionedProductCatalog() {
            this.current = new AtomicReference<>(new CatalogSnapshot());
        }

        private CatalogSnapshot snapshot() {
            return current.get();
        }

        Product get(int docId) {
            return snapshot().get(docId);
        }

        void add(int docId, Product product) {
            while (true) {
                CatalogSnapshot oldSnapshot = snapshot();
                CatalogSnapshot newSnapshot = oldSnapshot.add(docId, product);

                if(current.compareAndSet(
                        oldSnapshot,
                        newSnapshot
                )){
                    return;
                }
            }
        }

        void update(int docId, Product product) {
            while (true) {
                CatalogSnapshot oldSnapshot = snapshot();
                CatalogSnapshot newSnapshot = oldSnapshot.update(docId, product);

                if(current.compareAndSet(
                        oldSnapshot,
                        newSnapshot
                )){
                    return;
                }
            }
        }

        void remove(int docId) {
            while (true) {
                CatalogSnapshot oldSnapshot = snapshot();
                CatalogSnapshot newSnapshot = oldSnapshot.remove(docId);

                if(current.compareAndSet(
                        oldSnapshot,
                        newSnapshot
                )){
                    return;
                }
            }
        }
    }
    // endregion

    // region Mutation

    sealed interface CatalogMutation {
        record Add(
                int docId,
                Product product
        ) implements CatalogMutation {}

        record Update(
                int docId,
                Product product
        ) implements CatalogMutation {}

        record Remove(
                int docId
        ) implements CatalogMutation {}
    }
    record MutationTask(
            CatalogMutation mutation,
            CompletableFuture<Void> completion
    ) {}

    // endregion

    // region SnapshotUpdateEngine
    // queue + single writer thread
    static final class SnapshotUpdateEngine implements AutoCloseable {

        private final AtomicReference<CatalogSnapshot> current;
        private final BlockingQueue<MutationTask> queue;
        private final Thread writerThread;
        private volatile boolean running;

        private static final int QUEUE_CAPACITY = 100_000;

        private static final int MAX_BATCH_SIZE = 1000;
        private static final long MAX_BATCH_WAIT_MS = 5;

        SnapshotUpdateEngine() {
            this.current = new AtomicReference<>(new CatalogSnapshot());
            this.queue = new LinkedBlockingQueue<>(QUEUE_CAPACITY);
            this.running = true;
            this.writerThread = new Thread(this::runWriter);
            this.writerThread.start();
        }

        Product get(int docId) {
            return current.get().get(docId);
        }

        CatalogSnapshot snapshotForTest() {
            return current.get();
        }

        private CompletableFuture<Void> submit(
                CatalogMutation mutation
        ) {
            CompletableFuture<Void> future = new CompletableFuture<>();

            MutationTask task = new MutationTask(mutation, future);

            if (!running) {
                future.completeExceptionally(
                        new IllegalStateException("Engine closed")
                );
                return future;
            }

            if (!queue.offer(task)) {
                future.completeExceptionally(
                        new RejectedExecutionException(
                                "Mutation queue is full"
                        )
                );
            }

            return future;
        }

        CompletableFuture<Void> add(int docId, Product product) {
            return submit(new CatalogMutation.Add(docId, product));
        }

        CompletableFuture<Void> remove(int docId) {
            return submit(new CatalogMutation.Remove(docId));
        }

        CompletableFuture<Void> update(int docId, Product product) {
            return submit(new CatalogMutation.Update(docId, product));
        }

        private void runWriter() {
            while (running) {
                try {
                    List<MutationTask> batch = new ArrayList<>(MAX_BATCH_SIZE);
                    MutationTask first = queue.take();
                    batch.add(first);

                    long deadline = System.nanoTime()
                            + TimeUnit.MILLISECONDS.toNanos(MAX_BATCH_WAIT_MS);

                    while (batch.size() < MAX_BATCH_SIZE) {

                        queue.drainTo(
                                batch,
                                MAX_BATCH_SIZE - batch.size()
                        );

                        if (batch.size() >= MAX_BATCH_SIZE) {
                            break;
                        }

                        long remaining = deadline - System.nanoTime();

                        if (remaining <= 0) {
                            break;
                        }

                        MutationTask task = queue.poll(
                                remaining,
                                TimeUnit.NANOSECONDS
                        );

                        if (task == null) {
                            break;
                        }

                        batch.add(task);
                    }

                    processBatch(batch);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }

        private void processBatch(List<MutationTask> batch) {
            CatalogSnapshot base = current.get();
            CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(base);
            List<MutationTask> succeeded = new ArrayList<>();
            for (MutationTask task : batch) {
                try {
                    apply(builder, task.mutation());
                    succeeded.add(task);
                } catch (Exception e) {
                    task.completion().completeExceptionally(e);
                }
            }
            if(succeeded.isEmpty()){
                return;
            }
            CatalogSnapshot next = builder.build();
            current.set(next);
            for (MutationTask task : succeeded) {
                task.completion().complete(null);
            }
        }

        private void apply(
                CatalogSnapshotBuilder builder,
                CatalogMutation mutation
        ) {
            if (mutation instanceof CatalogMutation.Add add) {
                builder.add(add.docId(), add.product());
                return;
            }

            if (mutation instanceof CatalogMutation.Update update) {
                builder.update(update.docId(), update.product());
                return;
            }

            if (mutation instanceof CatalogMutation.Remove remove) {
                builder.remove(remove.docId());
                return;
            }

            throw new IllegalArgumentException("Unknown mutation");
        }

        @Override
        public void close() {
            running = false;
            writerThread.interrupt();

            InterruptedException exception =
                    new InterruptedException("SnapshotUpdateEngine closed");

            MutationTask task;

            while ((task = queue.poll()) != null) {
                task.completion().completeExceptionally(exception);
            }
        }

//        Optional<ImmutableBitmap> getCandidateBitmap(
//                ProductFilter filter
//        ) {
//            return current.get().getCandidates(filter);
//        }

        List<Product> search(ProductFilter filter) {
            Objects.requireNonNull(filter);

            CatalogSnapshot snapshot = current.get();

            Optional<CandidateResult> candidateResult = snapshot.getCandidates(filter);

            ImmutableBitmap candidates;

            if(candidateResult.isEmpty()){
                candidates = snapshot.activeProducts();
            }else {
                candidates = candidateResult.get().bitmap();
            }

            List<Product> result = new ArrayList<>();

            candidates.forEachSetBit(docId -> {

                Product product = snapshot.get(docId);

                if (product != null && filter.matches(product)) {
                    result.add(product);
                }
            });

            return result;
        }
    }
    // endregion

    // region ProductCatalog
    static class ProductCatalog {

        private final Map<String, Product> idToProduct;
        private final List<ProductIndex> indexes;
        private final Map<String, Integer> productIdToDocId;
        private final List<Product> docIdToProduct;
        private final BitSet activeProducts;
        private final ArrayDeque<Integer> unusedDocId;

        private final ReentrantReadWriteLock lock;
        private final Lock readLock;
        private final Lock writeLock;

        ProductCatalog(List<Product> products) {

            Objects.requireNonNull(products);

            this.lock = new ReentrantReadWriteLock();
            this.readLock = this.lock.readLock();
            this.writeLock = this.lock.writeLock();

            this.idToProduct = new HashMap<>();

            this.indexes = List.of(
                    new NamePrefixIndex(),
                    new CategoryIndex(),
                    new PrimeIndex(),
                    new PriceIndex()
            );

            this.productIdToDocId = new HashMap<>();
            this.docIdToProduct = new ArrayList<>();

            this.activeProducts = new BitSet();
            this.unusedDocId = new ArrayDeque<>();

            for (Product product : products) {
                try {
                    Utils.validateProd(product);
                    add(product);
                } catch (IllegalArgumentException e){
                    System.err.println(e.getMessage());
                }
            }
        }

        public void add(Product product) {
            Utils.validateProd(product);
            this.writeLock.lock();
            try{
                if(this.idToProduct.containsKey(product.id())){
                    throw new IllegalArgumentException("Product already exists!");
                }
                Integer queueDocId = this.unusedDocId.pollFirst();
                int docId = queueDocId == null ? this.docIdToProduct.size() : queueDocId;
                this.idToProduct.put(product.id(), product);
                this.productIdToDocId.put(product.id(), docId);
                if(docId < this.docIdToProduct.size()){
                    this.docIdToProduct.set(docId, product);
                }else{
                    this.docIdToProduct.add(product);
                }
                this.activeProducts.set(docId);
                for(ProductIndex index : this.indexes){
                    index.add(product, docId);
                }
            } finally {
                this.writeLock.unlock();
            }
        }

        public boolean remove(String productId) {
            Utils.validateStr(productId);
            this.writeLock.lock();
            try {
                Product product = this.idToProduct.remove(productId);
                if(product == null){
                    return false;
                }
                int docId = this.productIdToDocId.get(productId);
                this.productIdToDocId.remove(productId);
                this.docIdToProduct.set(docId, null);
                this.activeProducts.clear(docId);
                this.unusedDocId.offerLast(docId);
                for(ProductIndex index : this.indexes){
                    index.remove(product, docId);
                }
                return true;
            } finally {
                this.writeLock.unlock();
            }
        }

        public boolean update(Product product) {
            Utils.validateProd(product);
            String productId = product.id();
            this.writeLock.lock();
            try {
                Product oldProduct = this.idToProduct.get(productId);
                if(oldProduct == null){
                    return false;
                }
                int docId = this.productIdToDocId.get(productId);
                this.idToProduct.put(productId, product);
                this.docIdToProduct.set(docId, product);
                for(ProductIndex index : this.indexes){
                    index.update(oldProduct, product, docId);
                }
                return true;
            } finally {
                this.writeLock.unlock();
            }
        }

        public Product get(String id) {
            Utils.validateStr(id);
            this.readLock.lock();
            try {
                return this.idToProduct.get(id);
            } finally {
                this.readLock.unlock();
            }
        }

        public Product getByDocId(int docId) {
            this.readLock.lock();
            try {
                return this.docIdToProduct.get(docId);
            } finally {
                this.readLock.unlock();
            }
        }

        private Optional<BitSet> getCandidatesInternal(ProductFilter filter){
            Objects.requireNonNull(filter);
            if (filter instanceof AndFilter andFilter) {
                BitSet candidates = null;
                for (ProductFilter f : andFilter.filters()) {
                    Optional<BitSet> childSetOptional = getCandidatesInternal(f);
                    if (childSetOptional.isEmpty()) {
                        continue;
                    }
                    BitSet childSet = childSetOptional.get();
                    if (childSet.isEmpty()) {
                        return Optional.of(new BitSet());
                    }
                    if (candidates == null) {
                        candidates = (BitSet) childSet.clone();
                    } else {
                        candidates.and(childSet);
                    }
                }
                return candidates == null ? Optional.empty() : Optional.of(candidates);
            }
            if (filter instanceof OrFilter orFilter) {
                List<ProductFilter> filters = orFilter.filters();
                if (filters.isEmpty()) {
                    return Optional.of(new BitSet());
                }
                BitSet candidates = new BitSet();
                for (ProductFilter f : filters) {
                    Optional<BitSet> childrenSetOptional = getCandidatesInternal(f);
                    if (childrenSetOptional.isEmpty()) {
                        return Optional.empty();
                    }
                    BitSet childrenSet = childrenSetOptional.get();
                    candidates.or(childrenSet);
                }
                return Optional.of(candidates);
            }
            if (filter instanceof NotFilter) {
                return Optional.empty();
            }
            for (ProductIndex index : indexes) {
                Optional<BitSet> candidates = index.getCandidates(filter);
                if (candidates.isPresent()) {
                    return candidates;
                }
            }
            return Optional.empty();
        }

        private BitSet getAllProductBitSetInternal() {
            return (BitSet) this.activeProducts.clone();
        }

        public List<Product> search(ProductFilter filter) {
            Objects.requireNonNull(filter);
            List<Product> snapshot = new ArrayList<>();
            readLock.lock();
            try {
                BitSet candidates = getCandidatesInternal(filter)
                        .orElseGet(this::getAllProductBitSetInternal);

                for (
                        int docId = candidates.nextSetBit(0);
                        docId >= 0;
                        docId = candidates.nextSetBit(docId + 1)
                ) {
                    snapshot.add(this.docIdToProduct.get(docId));
                }
            } finally {
                readLock.unlock();
            }

            List<Product> res = new ArrayList<>();
            for(Product p : snapshot){
                if (filter.matches(p)) {
                    res.add(p);
                }
            }
            return res;
        }
    }
    // endregion

    // region ProductFilter

    interface ProductFilter {
        boolean matches(Product product);
    }
    record NameFilter(String prefix) implements ProductFilter {

        @Override
        public boolean matches(Product product) {
            return product.name().startsWith(this.prefix);
        }
    }
    record PriceRangeFilter(double minPrice, double maxPrice) implements ProductFilter {

        @Override
        public boolean matches(Product product) {
            return product.price() >= this.minPrice
                    && product.price() <= this.maxPrice;
        }
    }
    record CategoryFilter(Category category) implements ProductFilter {

        @Override
        public boolean matches(Product product) {
            return product.category() == this.category;
        }
    }
    record PrimeFilter(boolean requirePrime) implements ProductFilter {

        @Override
        public boolean matches(Product product) {
            return product.prime() == this.requirePrime;
        }
    }
    static class RatingFilter implements ProductFilter {

        private final double minRating;
        private final double maxRating;

        RatingFilter(double minRating) {
            this.minRating = minRating;
            this.maxRating = Double.MAX_VALUE;
        }

        RatingFilter(double minRating, double maxRating) {
            this.minRating = minRating;
            this.maxRating = maxRating;
        }

        @Override
        public boolean matches(Product product) {
            return product.rating() >= this.minRating
                    && product.rating() <= this.maxRating;
        }
    }
    record AndFilter(List<ProductFilter> filters) implements ProductFilter {

        AndFilter(List<ProductFilter> filters) {
            this.filters = List.copyOf(filters);
        }

        @Override
        public boolean matches(Product product) {
            for (ProductFilter filter : this.filters) {
                if (!filter.matches(product)) {
                    return false;
                }
            }
            return true;
        }

        @Override
        public List<ProductFilter> filters() {
            return List.copyOf(filters);
        }
    }
    record OrFilter(List<ProductFilter> filters) implements ProductFilter {

        OrFilter(List<ProductFilter> filters) {
            this.filters = List.copyOf(filters);
        }

        @Override
        public boolean matches(Product product) {
            for (ProductFilter filter : this.filters) {
                if (filter.matches(product)) {
                    return true;
                }
            }
            return false;
        }

        @Override
        public List<ProductFilter> filters() {
            return List.copyOf(this.filters);
        }
    }
    record NotFilter(ProductFilter filter) implements ProductFilter {

        @Override
        public boolean matches(Product product) {
            return !filter.matches(product);
        }
    }

    // endregion

    // region ProductFilterService

    static class ProductFilterService {

        private final ProductCatalog catalog;

        ProductFilterService(ProductCatalog catalog) {
            this.catalog = catalog;
        }

        List<Product> filter(ProductFilter filter){
            return this.catalog.search(filter);
        }
    }

    //endregion

    // region Utils

    static class Utils {
        public static void validateProd(
                String id,
                String name,
                Category category,
                double price,
                double rating
        ){
            Utils.validateStr(id, name);
            Objects.requireNonNull(category);
            if(price < 0 || rating < 0){
                throw new IllegalArgumentException();
            }
        }
        public static void validateProd(Product prod){
            validateProd(prod.id(), prod.name(), prod.category(), prod.price(), prod.rating());
        }
        public static void validateStr(String... strs){
            Objects.requireNonNull(strs);
            for(String str : strs){
                if(str == null || str.isBlank()){
                    throw new IllegalArgumentException();
                }
            }
        }
    }

    //endregion

    // =============== Test =======================

    public static void main(String[] args) throws Exception {

//        basicTest();
//        testPersistentTreeRandom();
//        testBitmapRandomDifferential();
        testLargeCatalogDifferential();
//        concurrentStressTest();

        System.out.println(
                "\nALL STRESS TESTS PASSED"
        );
    }

    // region test function

    public static void basicTest() {

        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine()) {

            Product laptop = new Product(
                    "P1",
                    "Laptop",
                    Category.ELECTRONICS,
                    999.99,
                    true,
                    4.6
            );

            Product headphones = new Product(
                    "P2",
                    "Headphones",
                    Category.ELECTRONICS,
                    79.99,
                    true,
                    4.4
            );

            Product keyboard = new Product(
                    "P3",
                    "Mechanical Keyboard",
                    Category.ELECTRONICS,
                    129.99,
                    false,
                    4.7
            );

            Product book = new Product(
                    "P4",
                    "Design Patterns",
                    Category.BOOKS,
                    49.99,
                    true,
                    4.8
            );

            Product tshirt = new Product(
                    "P5",
                    "T-Shirt",
                    Category.CLOTHING,
                    25.99,
                    false,
                    4.1
            );

            Product mouse = new Product(
                    "P6",
                    "Wireless Mouse",
                    Category.ELECTRONICS,
                    39.99,
                    true,
                    3.9
            );

            // =========================
            // 1. ADD
            // =========================

            CompletableFuture.allOf(
                    engine.add(0, laptop),
                    engine.add(1, headphones),
                    engine.add(2, keyboard),
                    engine.add(3, book),
                    engine.add(4, tshirt),
                    engine.add(5, mouse)
            ).join();

            // Electronics
            assertIds(
                    "Category ELECTRONICS",
                    engine.search(
                            new CategoryFilter(
                                    Category.ELECTRONICS
                            )
                    ),
                    "P1", "P2", "P3", "P6"
            );

            // Prime true
            assertIds(
                    "Prime=true",
                    engine.search(
                            new PrimeFilter(true)
                    ),
                    "P1", "P2", "P4", "P6"
            );

            // Prime false
            assertIds(
                    "Prime=false",
                    engine.search(
                            new PrimeFilter(false)
                    ),
                    "P3", "P5"
            );

            // =========================
            // 2. AND
            // =========================

            assertIds(
                    "Electronics AND Prime",
                    engine.search(
                            new AndFilter(
                                    List.of(
                                            new CategoryFilter(
                                                    Category.ELECTRONICS
                                            ),
                                            new PrimeFilter(true)
                                    )
                            )
                    ),
                    "P1", "P2", "P6"
            );

            // AND 中包含未索引 RatingFilter
            // candidate 应由 Category/Prime 缩小，
            // 最终 matches() 校验 rating。
            assertIds(
                    "Electronics AND Prime AND Rating>=4",
                    engine.search(
                            new AndFilter(
                                    List.of(
                                            new CategoryFilter(
                                                    Category.ELECTRONICS
                                            ),
                                            new PrimeFilter(true),
                                            new RatingFilter(4.0)
                                    )
                            )
                    ),
                    "P1", "P2"
            );

            // =========================
            // 3. OR
            // =========================

            assertIds(
                    "Books OR Prime=false",
                    engine.search(
                            new OrFilter(
                                    List.of(
                                            new CategoryFilter(
                                                    Category.BOOKS
                                            ),
                                            new PrimeFilter(false)
                                    )
                            )
                    ),
                    "P3", "P4", "P5"
            );

            // =========================
            // 4. FALLBACK FULL SCAN
            // =========================

            assertIds(
                    "Rating>=4.7",
                    engine.search(
                            new RatingFilter(4.7)
                    ),
                    "P3", "P4"
            );

            // =========================
            // 5. UPDATE CATEGORY
            // =========================

            Product updatedKeyboard = new Product(
                    "P3",
                    "Mechanical Keyboard",
                    Category.HOME,
                    129.99,
                    false,
                    4.7
            );

            engine.update(2, updatedKeyboard).join();

            assertIds(
                    "After category update - Electronics",
                    engine.search(
                            new CategoryFilter(
                                    Category.ELECTRONICS
                            )
                    ),
                    "P1", "P2", "P6"
            );

            assertIds(
                    "After category update - Home",
                    engine.search(
                            new CategoryFilter(
                                    Category.HOME
                            )
                    ),
                    "P3"
            );

            // =========================
            // 6. UPDATE PRIME
            // =========================

            Product updatedMouse = new Product(
                    "P6",
                    "Wireless Mouse",
                    Category.ELECTRONICS,
                    39.99,
                    false,
                    3.9
            );

            engine.update(5, updatedMouse).join();

            assertIds(
                    "After prime update - Prime=true",
                    engine.search(
                            new PrimeFilter(true)
                    ),
                    "P1", "P2", "P4"
            );

            assertIds(
                    "After prime update - Prime=false",
                    engine.search(
                            new PrimeFilter(false)
                    ),
                    "P3", "P5", "P6"
            );

            // =========================
            // 7. REMOVE
            // =========================

            engine.remove(1).join();

            assertIds(
                    "After remove P2",
                    engine.search(
                            new AndFilter(List.of())
                    ),
                    "P1", "P3", "P4", "P5", "P6"
            );

            assertIds(
                    "Electronics after remove P2",
                    engine.search(
                            new CategoryFilter(
                                    Category.ELECTRONICS
                            )
                    ),
                    "P1", "P6"
            );

            // =========================
            // 8. SAME BATCH STATE
            // =========================

            Product newProduct = new Product(
                    "P7",
                    "Camera",
                    Category.ELECTRONICS,
                    500.0,
                    true,
                    4.9
            );

            CompletableFuture<Void> add =
                    engine.add(6, newProduct);

            Product updatedProduct = new Product(
                    "P7",
                    "Camera",
                    Category.BEAUTY,
                    500.0,
                    false,
                    4.9
            );

            CompletableFuture<Void> update =
                    engine.update(6, updatedProduct);

            CompletableFuture.allOf(
                    add,
                    update
            ).join();

            assertIds(
                    "P7 final category",
                    engine.search(
                            new CategoryFilter(
                                    Category.BEAUTY
                            )
                    ),
                    "P7"
            );

            assertIds(
                    "P7 no longer Prime",
                    engine.search(
                            new AndFilter(
                                    List.of(
                                            new CategoryFilter(
                                                    Category.BEAUTY
                                            ),
                                            new PrimeFilter(false)
                                    )
                            )
                    ),
                    "P7"
            );

            System.out.println(
                    "\n============================"
            );
            System.out.println(
                    "ALL TESTS PASSED"
            );
            System.out.println(
                    "============================"
            );
        }
    }

    private static void concurrentStressTest() throws Exception {

        final int PRODUCT_COUNT = 100_000;

        final int WRITER_THREADS = 4;
        final int READER_THREADS = 8;

        final int WRITES_PER_THREAD = 20_000;
        final int READS_PER_THREAD = 1_000;

        System.out.println();
        System.out.println("==============================");
        System.out.println("Concurrent Reader/Writer Stress");
        System.out.println("==============================");

        SnapshotUpdateEngine engine =
                new SnapshotUpdateEngine();

        ExecutorService pool =
                Executors.newFixedThreadPool(
                        WRITER_THREADS
                                + READER_THREADS
                );

        AtomicReference<Throwable> failure =
                new AtomicReference<>();

        CountDownLatch start =
                new CountDownLatch(1);

        List<Future<?>> tasks =
                new ArrayList<>();

        try {

            // ==========================================
            // Phase 1: preload
            // ==========================================

            System.out.println(
                    "[INFO] Preloading "
                            + PRODUCT_COUNT
                            + " products"
            );

            List<CompletableFuture<Void>> pending =
                    new ArrayList<>();

            Random initRandom =
                    new Random(12345);

            for (int docId = 0;
                 docId < PRODUCT_COUNT;
                 docId++) {

                Product product =
                        randomProduct(
                                docId,
                                initRandom
                        );

                pending.add(
                        engine.add(
                                docId,
                                product
                        )
                );

                if (pending.size() >= 5_000) {

                    CompletableFuture.allOf(
                            pending.toArray(
                                    CompletableFuture[]::new
                            )
                    ).join();

                    pending.clear();
                }
            }

            if (!pending.isEmpty()) {
                CompletableFuture.allOf(
                        pending.toArray(
                                CompletableFuture[]::new
                        )
                ).join();
            }

            System.out.println(
                    "[PASS] preload completed"
            );

            // ==========================================
            // Phase 2: writer producers
            // ==========================================

            for (int writer = 0;
                 writer < WRITER_THREADS;
                 writer++) {

                final int writerId =
                        writer;

                tasks.add(
                        pool.submit(() -> {

                            Random random =
                                    new Random(
                                            10_000L
                                                    + writerId
                                    );

                            start.await();

                            for (
                                    int operation = 0;
                                    operation
                                            < WRITES_PER_THREAD;
                                    operation++
                            ) {

                                if (failure.get() != null) {
                                    return null;
                                }

                                int docId =
                                        random.nextInt(
                                                PRODUCT_COUNT
                                        );

                                try {

                                    Product currentProduct =
                                            engine.get(docId);

                                    int action =
                                            random.nextInt(100);

                                    if (currentProduct == null) {

                                        // -----------------
                                        // ADD BACK
                                        // -----------------

                                        Product newProduct =
                                                randomProduct(
                                                        docId,
                                                        random
                                                );

                                        engine.add(
                                                docId,
                                                newProduct
                                        ).join();

                                    } else if (action < 20) {

                                        // -----------------
                                        // REMOVE ~20%
                                        // -----------------

                                        engine.remove(
                                                docId
                                        ).join();

                                    } else {

                                        // -----------------
                                        // UPDATE ~80%
                                        // -----------------

                                        Product updated =
                                                randomUpdatedProduct(
                                                        currentProduct,
                                                        random
                                                );

                                        engine.update(
                                                docId,
                                                updated
                                        ).join();
                                    }

                                } catch (CompletionException e) {

                                    /*
                                     * 这是允许发生的竞争：
                                     *
                                     * Writer A:
                                     * get(docId) != null
                                     *
                                     * Writer B:
                                     * remove(docId)
                                     *
                                     * Writer A:
                                     * update(docId)
                                     *
                                     * update 进入 single writer 时，
                                     * 商品可能已经不存在。
                                     *
                                     * 这是 producer race，
                                     * 不是 snapshot engine correctness bug。
                                     */

                                    Throwable cause =
                                            e.getCause();

                                    if (!(cause
                                            instanceof IllegalStateException)) {

                                        throw e;
                                    }
                                }

                                if (
                                        operation > 0
                                                && operation % 5_000 == 0
                                ) {
                                    System.out.println(
                                            "[INFO] writer-"
                                                    + writerId
                                                    + " operations="
                                                    + operation
                                    );
                                }
                            }

                            return null;
                        })
                );
            }

            // ==========================================
            // Phase 3: readers
            // ==========================================

            for (int reader = 0;
                 reader < READER_THREADS;
                 reader++) {

                final int readerId =
                        reader;

                tasks.add(
                        pool.submit(() -> {

                            Random random =
                                    new Random(
                                            100_000L
                                                    + readerId
                                    );

                            start.await();

                            for (
                                    int query = 0;
                                    query < READS_PER_THREAD;
                                    query++
                            ) {

                                if (failure.get() != null) {
                                    return null;
                                }

                                try {

                                    // ==================================
                                    // 抓住一个固定 immutable snapshot
                                    // ==================================

                                    CatalogSnapshot snapshot =
                                            engine.snapshotForTest();

                                    ProductFilter filter =
                                            randomTestFilter(
                                                    random
                                            );

                                    Set<String> indexed =
                                            ids(
                                                    indexedSearchOnSnapshot(
                                                            snapshot,
                                                            filter
                                                    )
                                            );

                                    Set<String> brute =
                                            ids(
                                                    bruteForceSearchOnSnapshot(
                                                            snapshot,
                                                            filter,
                                                            PRODUCT_COUNT
                                                    )
                                            );

                                    if (!indexed.equals(brute)) {

                                        Set<String> missing =
                                                new HashSet<>(
                                                        brute
                                                );

                                        missing.removeAll(
                                                indexed
                                        );

                                        Set<String> unexpected =
                                                new HashSet<>(
                                                        indexed
                                                );

                                        unexpected.removeAll(
                                                brute
                                        );

                                        throw new AssertionError(
                                                "\nConcurrent search mismatch"
                                                        + "\nReader="
                                                        + readerId
                                                        + "\nFilter="
                                                        + filter
                                                        + "\nIndexed size="
                                                        + indexed.size()
                                                        + "\nBrute size="
                                                        + brute.size()
                                                        + "\nMissing="
                                                        + sampleSet(
                                                        missing,
                                                        10
                                                )
                                                        + "\nUnexpected="
                                                        + sampleSet(
                                                        unexpected,
                                                        10
                                                )
                                        );
                                    }

                                } catch (Throwable t) {

                                    failure.compareAndSet(
                                            null,
                                            t
                                    );

                                    throw t;
                                }

                                if (
                                        query > 0
                                                && query % 250 == 0
                                ) {
                                    System.out.println(
                                            "[INFO] reader-"
                                                    + readerId
                                                    + " queries="
                                                    + query
                                    );
                                }
                            }

                            return null;
                        })
                );
            }

            // ==========================================
            // GO
            // ==========================================

            long startTime =
                    System.nanoTime();

            start.countDown();

            // 等所有 producer + reader
            for (Future<?> task : tasks) {

                try {
                    task.get();

                } catch (ExecutionException e) {

                    Throwable cause =
                            e.getCause();

                    failure.compareAndSet(
                            null,
                            cause
                    );
                }
            }

            long elapsedNs =
                    System.nanoTime()
                            - startTime;

            if (failure.get() != null) {
                throw new AssertionError(
                        "Concurrent stress test failed",
                        failure.get()
                );
            }

            double elapsedSeconds =
                    elapsedNs / 1_000_000_000.0;

            System.out.printf(
                    Locale.US,
                    "[PASS] Concurrent stress completed in %.2f sec%n",
                    elapsedSeconds
            );

            System.out.println(
                    "[INFO] writer operations ~= "
                            + (
                            WRITER_THREADS
                                    * WRITES_PER_THREAD
                    )
            );

            System.out.println(
                    "[INFO] reader queries = "
                            + (
                            READER_THREADS
                                    * READS_PER_THREAD
                    )
            );

        } finally {

            pool.shutdownNow();

            engine.close();
        }
    }
    private static List<Product> indexedSearchOnSnapshot(
            CatalogSnapshot snapshot,
            ProductFilter filter
    ) {

        Optional<CandidateResult> candidateOpt =
                snapshot.getCandidates(filter);

        ImmutableBitmap candidates =
                candidateOpt
                        .map(CandidateResult::bitmap)
                        .orElse(
                                snapshot.activeProducts()
                        );

        List<Product> result =
                new ArrayList<>();

        candidates.forEachSetBit(
                docId -> {

                    Product product =
                            snapshot.get(docId);

                    if (
                            product != null
                                    && filter.matches(product)
                    ) {
                        result.add(product);
                    }
                }
        );

        return result;
    }
    private static List<Product> bruteForceSearchOnSnapshot(
            CatalogSnapshot snapshot,
            ProductFilter filter,
            int maxDocId
    ) {

        List<Product> result =
                new ArrayList<>();

        for (
                int docId = 0;
                docId < maxDocId;
                docId++
        ) {

            Product product =
                    snapshot.get(docId);

            if (
                    product != null
                            && filter.matches(product)
            ) {
                result.add(product);
            }
        }

        return result;
    }
    private static Set<String> ids(
            List<Product> products
    ) {

        Set<String> result =
                new HashSet<>();

        for (Product product : products) {
            result.add(
                    product.id()
            );
        }

        return result;
    }

    private static void testBitmapRandomDifferential() {

        final int OPERATIONS = 200_000;
        final int MAX_DOC_ID = 40_000_000;
        final long SEED = 123456789L;

        Random random = new Random(SEED);

        ImmutableBitmap bitmap =
                new ImmutableBitmap();

        BitSet oracle =
                new BitSet();

        System.out.println(
                "\n=============================="
        );
        System.out.println(
                "Bitmap Random Differential Test"
        );
        System.out.println(
                "=============================="
        );

        // ------------------------------------------
        // 先专门打重要边界
        // ------------------------------------------

        int[] boundaryDocIds = {
                0,
                1,

                1023,
                1024,
                1025,

                1024 * 31 - 1,
                1024 * 31,
                1024 * 32 - 1,
                1024 * 32,
                1024 * 32 + 1,

                1024 * 1023,
                1024 * 1024 - 1,
                1024 * 1024,
                1024 * 1024 + 1,

                1024 * 32767,
                1024 * 32768
        };

        for (int docId : boundaryDocIds) {

            bitmap =
                    bitmap.withSet(docId);

            oracle.set(docId);

            assertBitmapMatches(
                    bitmap,
                    oracle,
                    random,
                    MAX_DOC_ID
            );
        }

        System.out.println(
                "[PASS] Boundary set verification"
        );

        // 再清掉一部分边界
        for (int i = 0;
             i < boundaryDocIds.length;
             i += 2) {

            int docId =
                    boundaryDocIds[i];

            bitmap =
                    bitmap.withClear(docId);

            oracle.clear(docId);

            assertBitmapMatches(
                    bitmap,
                    oracle,
                    random,
                    MAX_DOC_ID
            );
        }

        System.out.println(
                "[PASS] Boundary clear verification"
        );

        // ------------------------------------------
        // Random fuzz
        // ------------------------------------------

        for (int operation = 1;
             operation <= OPERATIONS;
             operation++) {

            int op =
                    random.nextInt(100);

            /*
             * 0 ~ 44:
             * set
             *
             * 45 ~ 69:
             * clear
             *
             * 70 ~ 79:
             * AND
             *
             * 80 ~ 89:
             * OR
             *
             * 90 ~ 99:
             * AND NOT
             */

            if (op < 45) {

                // =========================
                // SET
                // =========================

                int docId =
                        randomDocId(
                                random,
                                MAX_DOC_ID
                        );

                bitmap =
                        bitmap.withSet(docId);

                oracle.set(docId);

            } else if (op < 70) {

                // =========================
                // CLEAR
                // =========================

                int docId =
                        randomDocId(
                                random,
                                MAX_DOC_ID
                        );

                bitmap =
                        bitmap.withClear(docId);

                oracle.clear(docId);

            } else {

                // =========================
                // bitmap binary operation
                // =========================

                BitmapPair other =
                        randomBitmap(
                                random,
                                MAX_DOC_ID
                        );

                if (op < 80) {

                    // ---------------------
                    // AND
                    // ---------------------

                    bitmap =
                            bitmap.and(
                                    other.bitmap()
                            );

                    oracle.and(
                            other.oracle()
                    );

                } else if (op < 90) {

                    // ---------------------
                    // OR
                    // ---------------------

                    bitmap =
                            bitmap.or(
                                    other.bitmap()
                            );

                    oracle.or(
                            other.oracle()
                    );

                } else {

                    // ---------------------
                    // AND NOT
                    // ---------------------

                    bitmap =
                            bitmap.andNot(
                                    other.bitmap()
                            );

                    oracle.andNot(
                            other.oracle()
                    );
                }
            }

            // --------------------------------------
            // 每轮抽查一些位置
            // --------------------------------------

            assertBitmapMatches(
                    bitmap,
                    oracle,
                    random,
                    MAX_DOC_ID
            );

            if (operation % 10_000 == 0) {
                System.out.println(
                        "[INFO] bitmap operations="
                                + operation
                                + "/"
                                + OPERATIONS
                                + ", cardinality="
                                + oracle.cardinality()
                );
            }
        }

        // ------------------------------------------
        // 最终完整 set-bit 比较
        // ------------------------------------------

        assertFullBitmapEquals(
                bitmap,
                oracle
        );

        if (bitmap.cardinality()
                != oracle.cardinality()) {

            throw new AssertionError(
                    "cardinality mismatch"
            );
        }

        System.out.println();
        System.out.println(
                "[PASS] Bitmap random differential test"
        );
    }
    record BitmapPair(
            ImmutableBitmap bitmap,
            BitSet oracle
    ) {}
    private static BitmapPair randomBitmap(
            Random random,
            int maxDocId
    ) {

        ImmutableBitmap bitmap =
                new ImmutableBitmap();

        BitSet oracle =
                new BitSet();

        /*
         * 不要每次生成特别大。
         * 这里随机生成 0~200 个 set bits，
         * 可以制造非常 sparse 的 bitmap。
         */
        int size =
                random.nextInt(201);

        for (int i = 0; i < size; i++) {

            int docId =
                    randomDocId(
                            random,
                            maxDocId
                    );

            bitmap =
                    bitmap.withSet(docId);

            oracle.set(docId);
        }

        return new BitmapPair(
                bitmap,
                oracle
        );
    }
    private static int randomDocId(
            Random random,
            int maxDocId
    ) {

        if (random.nextInt(4) == 0) {

            int[] interesting = {
                    0,
                    1,

                    1023,
                    1024,
                    1025,

                    1024 * 31 - 1,
                    1024 * 31,
                    1024 * 32 - 1,
                    1024 * 32,
                    1024 * 32 + 1,

                    1024 * 1023,
                    1024 * 1024 - 1,
                    1024 * 1024,
                    1024 * 1024 + 1,

                    1024 * 32767,
                    1024 * 32768
            };

            return interesting[
                    random.nextInt(
                            interesting.length
                    )
                    ];
        }

        return random.nextInt(
                maxDocId
        );
    }
    private static void assertBitmapMatches(
            ImmutableBitmap bitmap,
            BitSet oracle,
            Random random,
            int maxDocId
    ) {

        // ------------------------------------------
        // isEmpty
        // ------------------------------------------

        if (bitmap.isEmpty()
                != oracle.isEmpty()) {

            throw new AssertionError(
                    "isEmpty mismatch"
                            + "\nImmutableBitmap="
                            + bitmap.isEmpty()
                            + "\nBitSet="
                            + oracle.isEmpty()
            );
        }

        // ------------------------------------------
        // 随机 get() 抽查
        // ------------------------------------------

        for (int i = 0; i < 50; i++) {

            int docId =
                    randomDocId(
                            random,
                            maxDocId
                    );

            boolean actual =
                    bitmap.get(docId);

            boolean expected =
                    oracle.get(docId);

            if (actual != expected) {

                throw new AssertionError(
                        "Bitmap get mismatch"
                                + "\ndocId="
                                + docId
                                + "\nexpected="
                                + expected
                                + "\nactual="
                                + actual
                );
            }
        }
    }
    private static void assertFullBitmapEquals(
            ImmutableBitmap bitmap,
            BitSet oracle
    ) {

        BitSet actual =
                new BitSet();

        bitmap.forEachSetBit(
                actual::set
        );

        if (!actual.equals(oracle)) {

            BitSet missing =
                    (BitSet) oracle.clone();

            missing.andNot(actual);

            BitSet unexpected =
                    (BitSet) actual.clone();

            unexpected.andNot(oracle);

            throw new AssertionError(
                    "Full bitmap mismatch"
                            + "\nExpected cardinality="
                            + oracle.cardinality()
                            + "\nActual cardinality="
                            + actual.cardinality()
                            + "\nMissing="
                            + sampleBits(
                            missing,
                            20
                    )
                            + "\nUnexpected="
                            + sampleBits(
                            unexpected,
                            20
                    )
            );
        }
    }
    private static List<Integer> sampleBits(
            BitSet bits,
            int limit
    ) {

        List<Integer> result =
                new ArrayList<>();

        for (
                int bit = bits.nextSetBit(0);
                bit >= 0
                        && result.size() < limit;
                bit = bits.nextSetBit(bit + 1)
        ) {
            result.add(bit);
        }

        return result;
    }

    private static void testLargeCatalogDifferential() {

        final int PRODUCT_COUNT = 100_000;
        final int MUTATION_COUNT = 30_000;
        final int QUERY_EVERY = 50;
        final int QUERIES_PER_CHECK = 5;

        final long SEED = 42L;

        Random random = new Random(SEED);

        // 最简单、最可信的 oracle：
        // oracle[docId] == null 表示该商品已删除
        Product[] oracle = new Product[PRODUCT_COUNT];

        System.out.println("\n==============================");
        System.out.println("Large Catalog Differential Test");
        System.out.println("==============================");

        try (SnapshotUpdateEngine engine =
                     new SnapshotUpdateEngine()) {

            // ==========================================
            // Phase 1: preload 100,000 products
            // ==========================================

            List<CompletableFuture<Void>> pending =
                    new ArrayList<>();

            for (int docId = 0;
                 docId < PRODUCT_COUNT;
                 docId++) {

                Product product =
                        randomProduct(docId, random);

                oracle[docId] = product;

                pending.add(
                        engine.add(docId, product)
                );

                // 不要一次保存 100k 个 future
                if (pending.size() == 5_000) {
                    CompletableFuture.allOf(
                            pending.toArray(
                                    CompletableFuture[]::new
                            )
                    ).join();

                    pending.clear();
                }
            }

            if (!pending.isEmpty()) {
                CompletableFuture.allOf(
                        pending.toArray(
                                CompletableFuture[]::new
                        )
                ).join();
            }

            System.out.println(
                    "[INFO] Loaded "
                            + PRODUCT_COUNT
                            + " products"
            );

            // 先做一次完整验证
            for (int i = 0; i < 20; i++) {
                ProductFilter filter =
                        randomTestFilter(random);

                assertSearchMatchesOracle(
                        engine,
                        oracle,
                        filter
                );
            }

            System.out.println(
                    "[PASS] Initial catalog verification"
            );

            // ==========================================
            // Phase 2: random mutations
            // ==========================================

            int addCount = 0;
            int updateCount = 0;
            int removeCount = 0;

            for (int mutation = 1;
                 mutation <= MUTATION_COUNT;
                 mutation++) {

                int docId =
                        random.nextInt(PRODUCT_COUNT);

                Product oldProduct =
                        oracle[docId];

                /*
                 * oracle == null:
                 *     这个 docId 当前已删除，只能 add-back
                 *
                 * oracle != null:
                 *     随机 update / remove
                 */
                if (oldProduct == null) {

                    Product newProduct =
                            randomProduct(
                                    docId,
                                    random
                            );

                    engine.add(
                            docId,
                            newProduct
                    ).join();

                    oracle[docId] =
                            newProduct;

                    addCount++;

                } else {

                    int operation =
                            random.nextInt(100);

                    if (operation < 25) {

                        // -----------------------
                        // REMOVE 25%
                        // -----------------------

                        engine.remove(docId).join();

                        oracle[docId] = null;

                        removeCount++;

                    } else {

                        // -----------------------
                        // UPDATE 75%
                        // -----------------------

                        Product newProduct =
                                randomUpdatedProduct(
                                        oldProduct,
                                        random
                                );

                        engine.update(
                                docId,
                                newProduct
                        ).join();

                        oracle[docId] =
                                newProduct;

                        updateCount++;
                    }
                }

                // ======================================
                // 每隔一段 mutation 做 differential query
                // ======================================

                if (mutation % QUERY_EVERY == 0) {

                    for (int q = 0;
                         q < QUERIES_PER_CHECK;
                         q++) {

                        ProductFilter filter =
                                randomTestFilter(random);

                        assertSearchMatchesOracle(
                                engine,
                                oracle,
                                filter
                        );
                    }
                }

                if (mutation % 5_000 == 0) {
                    System.out.println(
                            "[INFO] mutations="
                                    + mutation
                                    + "/"
                                    + MUTATION_COUNT
                    );
                }
            }

            // ==========================================
            // Phase 3: final heavy verification
            // ==========================================

            for (int i = 0; i < 200; i++) {
                ProductFilter filter =
                        randomTestFilter(random);

                assertSearchMatchesOracle(
                        engine,
                        oracle,
                        filter
                );
            }

            // 再直接检查每个 docId 的 Product
            for (int docId = 0;
                 docId < PRODUCT_COUNT;
                 docId++) {

                Product expected =
                        oracle[docId];

                Product actual =
                        engine.get(docId);

                if (!Objects.equals(
                        expected,
                        actual
                )) {
                    throw new AssertionError(
                            "Product mismatch at docId="
                                    + docId
                                    + "\nExpected: "
                                    + expected
                                    + "\nActual: "
                                    + actual
                    );
                }
            }

            System.out.println();
            System.out.println(
                    "[PASS] Product table matches oracle"
            );

            System.out.println(
                    "[PASS] Large catalog differential test"
            );

            System.out.println(
                    "Add-back: " + addCount
                            + ", Update: " + updateCount
                            + ", Remove: " + removeCount
            );
        }
    }
    private static Product randomProduct(
            int docId,
            Random random
    ) {

        Category[] categories =
                Category.values();

        return new Product(
                "P" + docId,

                "Product-" + docId
                        + "-"
                        + random.nextInt(10_000),

                categories[
                        random.nextInt(
                                categories.length
                        )
                        ],

                Math.round(
                        random.nextDouble()
                                * 200_000
                ) / 100.0,

                random.nextBoolean(),

                1.0
                        + random.nextDouble()
                        * 4.0
        );
    }
    private static Product randomUpdatedProduct(
            Product oldProduct,
            Random random
    ) {

        Category[] categories =
                Category.values();

        int updateType =
                random.nextInt(5);

        return switch (updateType) {

            // 只改 category
            case 0 -> new Product(
                    oldProduct.id(),
                    oldProduct.name(),
                    categories[
                            random.nextInt(
                                    categories.length
                            )
                            ],
                    oldProduct.price(),
                    oldProduct.prime(),
                    oldProduct.rating()
            );

            // 只改 prime
            case 1 -> new Product(
                    oldProduct.id(),
                    oldProduct.name(),
                    oldProduct.category(),
                    oldProduct.price(),
                    !oldProduct.prime(),
                    oldProduct.rating()
            );

            // 只改 rating
            case 2 -> new Product(
                    oldProduct.id(),
                    oldProduct.name(),
                    oldProduct.category(),
                    oldProduct.price(),
                    oldProduct.prime(),
                    1.0
                            + random.nextDouble()
                            * 4.0
            );

            // 同时改 category + prime
            case 3 -> new Product(
                    oldProduct.id(),
                    oldProduct.name(),
                    categories[
                            random.nextInt(
                                    categories.length
                            )
                            ],
                    oldProduct.price(),
                    !oldProduct.prime(),
                    oldProduct.rating()
            );

            // 大范围改动
            default -> randomProduct(
                    Integer.parseInt(
                            oldProduct.id()
                                    .substring(1)
                    ),
                    random
            );
        };
    }
    private static void assertSearchMatchesOracle(
            SnapshotUpdateEngine engine,
            Product[] oracle,
            ProductFilter filter
    ) {

        List<Product> indexedResult =
                engine.search(filter);

        Set<String> actualIds =
                new HashSet<>();

        for (Product product : indexedResult) {
            actualIds.add(product.id());
        }

        // ==========================================
        // Oracle 完全不使用：
        // - CategoryIndex
        // - PrimeIndex
        // - ImmutableBitmap
        // - PersistentBlockTree
        // - getCandidates()
        //
        // 就傻傻地全扫描。
        // ==========================================

        Set<String> expectedIds =
                new HashSet<>();

        for (Product product : oracle) {

            if (product == null) {
                continue;
            }

            if (filter.matches(product)) {
                expectedIds.add(
                        product.id()
                );
            }
        }

        if (!actualIds.equals(expectedIds)) {

            Set<String> missing =
                    new HashSet<>(expectedIds);

            missing.removeAll(actualIds);

            Set<String> unexpected =
                    new HashSet<>(actualIds);

            unexpected.removeAll(expectedIds);

            throw new AssertionError(
                    "\nDifferential search mismatch"
                            + "\nFilter: "
                            + filter
                            + "\nExpected size: "
                            + expectedIds.size()
                            + "\nActual size: "
                            + actualIds.size()
                            + "\nMissing sample: "
                            + sampleSet(missing, 10)
                            + "\nUnexpected sample: "
                            + sampleSet(
                            unexpected,
                            10
                    )
            );
        }
    }
    private static <T> List<T> sampleSet(
            Set<T> set,
            int limit
    ) {
        List<T> result =
                new ArrayList<>(limit);

        for (T value : set) {
            result.add(value);

            if (result.size() >= limit) {
                break;
            }
        }

        return result;
    }
    private static ProductFilter randomTestFilter(
            Random random
    ) {

        Category[] categories =
                Category.values();

        Category c1 =
                categories[
                        random.nextInt(
                                categories.length
                        )
                        ];

        Category c2 =
                categories[
                        random.nextInt(
                                categories.length
                        )
                        ];

        boolean prime =
                random.nextBoolean();

        double rating =
                3.0
                        + random.nextDouble()
                        * 2.0;

        return switch (
                random.nextInt(18)
                ) {

            // ==========================================
            // Basic EXACT indexed filters
            // ==========================================

            case 0 ->
                    new CategoryFilter(c1);

            case 1 ->
                    new PrimeFilter(prime);

            // ==========================================
            // Completely unindexed
            // ==========================================

            case 2 ->
                    new RatingFilter(rating);

            // ==========================================
            // EXACT AND
            // ==========================================

            case 3 ->
                    new AndFilter(
                            List.of(
                                    new CategoryFilter(c1),
                                    new PrimeFilter(prime)
                            )
                    );

            // ==========================================
            // SUPERSET AND
            //
            // RatingFilter 无 index，
            // 所以 planner 应该返回 indexed 条件交集，
            // accuracy = SUPERSET
            // ==========================================

            case 4 ->
                    new AndFilter(
                            List.of(
                                    new CategoryFilter(c1),
                                    new PrimeFilter(prime),
                                    new RatingFilter(rating)
                            )
                    );

            // ==========================================
            // EXACT OR
            // ==========================================

            case 5 ->
                    new OrFilter(
                            List.of(
                                    new CategoryFilter(c1),
                                    new PrimeFilter(prime)
                            )
                    );

            case 6 ->
                    new OrFilter(
                            List.of(
                                    new CategoryFilter(c1),
                                    new CategoryFilter(c2)
                            )
                    );

            // ==========================================
            // OR with unindexed child
            //
            // 整个 OR 应 fallback，
            // 因为不能只拿 indexed branch 做 candidate
            // ==========================================

            case 7 ->
                    new OrFilter(
                            List.of(
                                    new CategoryFilter(c1),
                                    new RatingFilter(rating)
                            )
                    );

            // ==========================================
            // NOT(EXACT)
            //
            // 应该可以：
            // active AND NOT categoryBitmap
            // ==========================================

            case 8 ->
                    new NotFilter(
                            new CategoryFilter(c1)
                    );

            case 9 ->
                    new NotFilter(
                            new PrimeFilter(prime)
                    );

            // ==========================================
            // NOT(EXACT composite)
            //
            // inner OR 是 EXACT，
            // 所以 NOT 也应该 EXACT
            // ==========================================

            case 10 ->
                    new NotFilter(
                            new OrFilter(
                                    List.of(
                                            new CategoryFilter(c1),
                                            new PrimeFilter(prime)
                                    )
                            )
                    );

            // ==========================================
            // NOT(SUPERSET)
            //
            // inner AND 因 RatingFilter 无索引，
            // candidate 是 SUPERSET。
            //
            // NOT 不能安全 complement，
            // 应 fallback full scan。
            // ==========================================

            case 11 ->
                    new NotFilter(
                            new AndFilter(
                                    List.of(
                                            new CategoryFilter(c1),
                                            new RatingFilter(rating)
                                    )
                            )
                    );

            // ==========================================
            // Nested:
            //
            // (Category c1 OR Category c2)
            // AND Prime
            //
            // 全部 indexed => EXACT
            // ==========================================

            case 12 ->
                    new AndFilter(
                            List.of(
                                    new OrFilter(
                                            List.of(
                                                    new CategoryFilter(c1),
                                                    new CategoryFilter(c2)
                                            )
                                    ),
                                    new PrimeFilter(prime)
                            )
                    );

            // ==========================================
            // More complex nested NOT
            //
            // Category
            // AND
            // NOT Prime
            //
            // 都可以用 EXACT bitmap
            // ==========================================

            case 13 ->
                    new AndFilter(
                            List.of(
                                    new CategoryFilter(c1),
                                    new NotFilter(
                                            new PrimeFilter(prime)
                                    )
                            )
                    );

            // ==========================================
            // Nested OR containing a SUPERSET child
            //
            // child1:
            // AND(Category, Rating)
            // => SUPERSET
            //
            // OR(SUPERSET, Prime)
            // => SUPERSET
            // ==========================================

            case 14 ->
                    new OrFilter(
                            List.of(
                                    new AndFilter(
                                            List.of(
                                                    new CategoryFilter(c1),
                                                    new RatingFilter(rating)
                                            )
                                    ),
                                    new PrimeFilter(prime)
                            )
                    );

            case 16 ->
                    new AndFilter(
                            List.of()
                    );

            case 17 ->
                    new OrFilter(
                            List.of()
                    );

            // ==========================================
            // Deep nested:
            //
            // NOT(
            //     (Category c1 OR Category c2)
            //     AND Prime
            // )
            //
            // inner 全 EXACT，所以 NOT 可优化
            // ==========================================

            default ->
                    new NotFilter(
                            new AndFilter(
                                    List.of(
                                            new OrFilter(
                                                    List.of(
                                                            new CategoryFilter(c1),
                                                            new CategoryFilter(c2)
                                                    )
                                            ),
                                            new PrimeFilter(prime)
                                    )
                            )
                    );
        };
    }

    private static void testPersistentTreeRandom() {

        PersistentBlockTree<Integer> tree =
                new PersistentBlockTree<>();

        Map<Integer, Integer> oracle =
                new HashMap<>();

        Random random = new Random(42);

        int[] boundaryIndexes = {
                0, 1,
                30, 31, 32, 33,
                1022, 1023, 1024, 1025,
                32766, 32767, 32768
        };

        for (int index : boundaryIndexes) {
            tree = tree.with(index, index);
            oracle.put(index, index);
        }

        for (int i = 0; i < 100_000; i++) {

            int index = random.nextInt(50_000);

            if (random.nextBoolean()) {
                int value = random.nextInt();

                tree = tree.with(index, value);
                oracle.put(index, value);

            } else {
                tree = tree.with(index, null);
                oracle.remove(index);
            }

            // 随机抽查
            for (int j = 0; j < 20; j++) {
                int testIndex =
                        random.nextInt(50_000);

                Integer expected =
                        oracle.get(testIndex);

                Integer actual =
                        tree.get(testIndex);

                if (!Objects.equals(expected, actual)) {
                    throw new AssertionError(
                            "Tree mismatch index="
                                    + testIndex
                                    + ", expected=" + expected
                                    + ", actual=" + actual
                    );
                }
            }
        }

        System.out.println(
                "[PASS] PersistentBlockTree random differential"
        );
    }

    private static List<Product> getProducts() {
        Product laptop = new Product(
                "P1",
                "Laptop",
                Category.ELECTRONICS,
                999.99,
                true,
                4.6
        );

        Product headphones = new Product(
                "P2",
                "Headphones",
                Category.ELECTRONICS,
                79.99,
                true,
                4.4
        );

        Product keyboard = new Product(
                "P3",
                "Mechanical Keyboard",
                Category.ELECTRONICS,
                129.99,
                false,
                4.7
        );

        Product book = new Product(
                "P4",
                "Design Patterns",
                Category.BOOKS,
                49.99,
                true,
                4.8
        );

        Product tshirt = new Product(
                "P5",
                "T-Shirt",
                Category.CLOTHING,
                25.99,
                false,
                4.1
        );

        Product mouse = new Product(
                "P6",
                "Wireless Mouse",
                Category.ELECTRONICS,
                39.99,
                true,
                3.9
        );

        return List.of(
                laptop,
                headphones,
                keyboard,
                book,
                tshirt,
                mouse
        );
    }

    private static void print(String name, List<Product> products) {
        System.out.println("\n" + name);

        if (products == null) {
            System.out.println("null");
            return;
        }

        for (Product product : products) {
            System.out.println(
                    product.id() + " - " + product.name()
            );
        }
    }

    private static void assertIds(
            String testName,
            List<Product> actual,
            String... expectedIds
    ) {
        Set<String> actualIds =
                new HashSet<>();

        for (Product product : actual) {
            actualIds.add(product.id());
        }

        Set<String> expected =
                new HashSet<>(
                        Arrays.asList(expectedIds)
                );

        if (!actualIds.equals(expected)) {
            throw new AssertionError(
                    testName
                            + "\nExpected: " + expected
                            + "\nActual:   " + actualIds
            );
        }

        System.out.println(
                "[PASS] "
                        + testName
                        + " -> "
                        + actualIds
        );
    }

    // endregion
}