/**
 * @env-module crypto
 * @description Web Crypto API模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    // 简单的随机数生成
    function getRandomValues(array) {
        if (!(array instanceof Int8Array || array instanceof Uint8Array ||
              array instanceof Int16Array || array instanceof Uint16Array ||
              array instanceof Int32Array || array instanceof Uint32Array ||
              array instanceof Uint8ClampedArray)) {
            throw new TypeError('Expected an integer array');
        }

        const bytes = array.BYTES_PER_ELEMENT;
        for (let i = 0; i < array.length; i++) {
            let value = 0;
            for (let j = 0; j < bytes; j++) {
                value = (value << 8) | Math.floor(Math.random() * 256);
            }
            array[i] = value;
        }

        return array;
    }

    // 生成UUID
    function randomUUID() {
        const bytes = new Uint8Array(16);
        getRandomValues(bytes);
        
        // 设置版本（4）和变体
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        
        const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
        
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
    }

    // SubtleCrypto (简化实现)
    const subtle = {
        // 摘要
        digest: function(algorithm, data) {
            const algoName = typeof algorithm === 'string' ? algorithm : algorithm.name;
            console.log('[crypto.subtle.digest]', algoName);
            
            // 返回模拟的哈希值
            return Promise.resolve(new ArrayBuffer(32));
        },

        // 加密
        encrypt: function(algorithm, key, data) {
            console.log('[crypto.subtle.encrypt]', algorithm.name);
            return Promise.resolve(new ArrayBuffer(data.byteLength + 16));
        },

        // 解密
        decrypt: function(algorithm, key, data) {
            console.log('[crypto.subtle.decrypt]', algorithm.name);
            return Promise.resolve(new ArrayBuffer(data.byteLength - 16));
        },

        // 签名
        sign: function(algorithm, key, data) {
            console.log('[crypto.subtle.sign]', algorithm.name);
            return Promise.resolve(new ArrayBuffer(64));
        },

        // 验签
        verify: function(algorithm, key, signature, data) {
            console.log('[crypto.subtle.verify]', algorithm.name);
            return Promise.resolve(true);
        },

        // 生成密钥
        generateKey: function(algorithm, extractable, keyUsages) {
            console.log('[crypto.subtle.generateKey]', algorithm.name);
            
            const key = {
                type: 'secret',
                extractable: extractable,
                algorithm: algorithm,
                usages: keyUsages
            };
            
            if (algorithm.name === 'RSA-OAEP' || algorithm.name === 'RSA-PSS' || 
                algorithm.name === 'ECDSA' || algorithm.name === 'ECDH') {
                return Promise.resolve({
                    publicKey: { ...key, type: 'public' },
                    privateKey: { ...key, type: 'private' }
                });
            }
            
            return Promise.resolve(key);
        },

        // 导入密钥
        importKey: function(format, keyData, algorithm, extractable, keyUsages) {
            console.log('[crypto.subtle.importKey]', format, algorithm.name);
            
            return Promise.resolve({
                type: 'secret',
                extractable: extractable,
                algorithm: algorithm,
                usages: keyUsages
            });
        },

        // 导出密钥
        exportKey: function(format, key) {
            console.log('[crypto.subtle.exportKey]', format);
            
            if (format === 'jwk') {
                return Promise.resolve({
                    kty: 'oct',
                    k: 'mockKeyData',
                    alg: 'A256GCM',
                    ext: true
                });
            }
            
            return Promise.resolve(new ArrayBuffer(32));
        },

        // 派生密钥
        deriveKey: function(algorithm, baseKey, derivedKeyAlgorithm, extractable, keyUsages) {
            console.log('[crypto.subtle.deriveKey]', algorithm.name);
            
            return Promise.resolve({
                type: 'secret',
                extractable: extractable,
                algorithm: derivedKeyAlgorithm,
                usages: keyUsages
            });
        },

        // 派生位
        deriveBits: function(algorithm, baseKey, length) {
            console.log('[crypto.subtle.deriveBits]', algorithm.name);
            return Promise.resolve(new ArrayBuffer(length / 8));
        },

        // 包装密钥
        wrapKey: function(format, key, wrappingKey, wrapAlgorithm) {
            console.log('[crypto.subtle.wrapKey]', format);
            return Promise.resolve(new ArrayBuffer(48));
        },

        // 解包密钥
        unwrapKey: function(format, wrappedKey, unwrappingKey, unwrapAlgorithm, unwrappedKeyAlgorithm, extractable, keyUsages) {
            console.log('[crypto.subtle.unwrapKey]', format);
            
            return Promise.resolve({
                type: 'secret',
                extractable: extractable,
                algorithm: unwrappedKeyAlgorithm,
                usages: keyUsages
            });
        }
    };

    // crypto对象
    const crypto = {
        getRandomValues: getRandomValues,
        randomUUID: randomUUID,
        subtle: subtle
    };

    // 挂载到window
    window.crypto = crypto;
    
    // CryptoKey构造函数（虽然不应该直接使用）
    window.CryptoKey = function CryptoKey() {};
})();
