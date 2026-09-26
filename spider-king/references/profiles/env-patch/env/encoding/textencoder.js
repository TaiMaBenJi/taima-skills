/**
 * @env-module TextEncoder/TextDecoder
 * @description 文本编解码器模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    // TextEncoder
    function TextEncoder() {
        this.encoding = 'utf-8';
    }

    TextEncoder.prototype = {
        encode: function(str) {
            if (typeof str !== 'string') {
                str = String(str);
            }
            
            const bytes = [];
            
            for (let i = 0; i < str.length; i++) {
                let charCode = str.charCodeAt(i);
                
                // 处理代理对（surrogate pairs）
                if (charCode >= 0xD800 && charCode <= 0xDBFF && i + 1 < str.length) {
                    const nextCharCode = str.charCodeAt(i + 1);
                    if (nextCharCode >= 0xDC00 && nextCharCode <= 0xDFFF) {
                        charCode = ((charCode - 0xD800) << 10) + (nextCharCode - 0xDC00) + 0x10000;
                        i++;
                    }
                }
                
                if (charCode < 0x80) {
                    bytes.push(charCode);
                } else if (charCode < 0x800) {
                    bytes.push(0xC0 | (charCode >> 6));
                    bytes.push(0x80 | (charCode & 0x3F));
                } else if (charCode < 0x10000) {
                    bytes.push(0xE0 | (charCode >> 12));
                    bytes.push(0x80 | ((charCode >> 6) & 0x3F));
                    bytes.push(0x80 | (charCode & 0x3F));
                } else {
                    bytes.push(0xF0 | (charCode >> 18));
                    bytes.push(0x80 | ((charCode >> 12) & 0x3F));
                    bytes.push(0x80 | ((charCode >> 6) & 0x3F));
                    bytes.push(0x80 | (charCode & 0x3F));
                }
            }
            
            return new Uint8Array(bytes);
        },

        encodeInto: function(str, destination) {
            const encoded = this.encode(str);
            const written = Math.min(encoded.length, destination.length);
            
            for (let i = 0; i < written; i++) {
                destination[i] = encoded[i];
            }
            
            return {
                read: str.length,
                written: written
            };
        }
    };

    // TextDecoder
    function TextDecoder(encoding, options) {
        encoding = (encoding || 'utf-8').toLowerCase();
        
        // 支持的编码别名
        const encodingMap = {
            'utf-8': 'utf-8',
            'utf8': 'utf-8',
            'unicode-1-1-utf-8': 'utf-8',
            'ascii': 'ascii',
            'us-ascii': 'ascii',
            'iso-8859-1': 'iso-8859-1',
            'latin1': 'iso-8859-1',
            'windows-1252': 'windows-1252',
            'gbk': 'gbk',
            'gb2312': 'gbk',
            'gb18030': 'gb18030'
        };
        
        this.encoding = encodingMap[encoding] || 'utf-8';
        this.fatal = options?.fatal || false;
        this.ignoreBOM = options?.ignoreBOM || false;
    }

    TextDecoder.prototype = {
        decode: function(input, options) {
            if (!input) {
                return '';
            }
            
            let bytes;
            if (input instanceof ArrayBuffer) {
                bytes = new Uint8Array(input);
            } else if (ArrayBuffer.isView(input)) {
                bytes = new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
            } else {
                throw new TypeError('Input must be an ArrayBuffer or ArrayBufferView');
            }
            
            // UTF-8解码
            if (this.encoding === 'utf-8') {
                return this._decodeUTF8(bytes);
            }
            
            // ASCII解码
            if (this.encoding === 'ascii') {
                return this._decodeASCII(bytes);
            }
            
            // ISO-8859-1解码
            if (this.encoding === 'iso-8859-1') {
                return this._decodeISO88591(bytes);
            }
            
            // 默认使用UTF-8
            return this._decodeUTF8(bytes);
        },

        _decodeUTF8: function(bytes) {
            let str = '';
            let i = 0;
            
            // 跳过BOM
            if (!this.ignoreBOM && bytes.length >= 3 && 
                bytes[0] === 0xEF && bytes[1] === 0xBB && bytes[2] === 0xBF) {
                i = 3;
            }
            
            while (i < bytes.length) {
                const byte1 = bytes[i++];
                
                if (byte1 < 0x80) {
                    str += String.fromCharCode(byte1);
                } else if ((byte1 & 0xE0) === 0xC0) {
                    const byte2 = bytes[i++];
                    const charCode = ((byte1 & 0x1F) << 6) | (byte2 & 0x3F);
                    str += String.fromCharCode(charCode);
                } else if ((byte1 & 0xF0) === 0xE0) {
                    const byte2 = bytes[i++];
                    const byte3 = bytes[i++];
                    const charCode = ((byte1 & 0x0F) << 12) | ((byte2 & 0x3F) << 6) | (byte3 & 0x3F);
                    str += String.fromCharCode(charCode);
                } else if ((byte1 & 0xF8) === 0xF0) {
                    const byte2 = bytes[i++];
                    const byte3 = bytes[i++];
                    const byte4 = bytes[i++];
                    let charCode = ((byte1 & 0x07) << 18) | ((byte2 & 0x3F) << 12) | ((byte3 & 0x3F) << 6) | (byte4 & 0x3F);
                    
                    // 处理超出BMP的字符（使用代理对）
                    if (charCode > 0xFFFF) {
                        charCode -= 0x10000;
                        str += String.fromCharCode(0xD800 + (charCode >> 10));
                        str += String.fromCharCode(0xDC00 + (charCode & 0x3FF));
                    } else {
                        str += String.fromCharCode(charCode);
                    }
                } else {
                    // 无效字节
                    if (this.fatal) {
                        throw new TypeError('Invalid UTF-8 sequence');
                    }
                    str += '\uFFFD'; // 替换字符
                }
            }
            
            return str;
        },

        _decodeASCII: function(bytes) {
            let str = '';
            for (let i = 0; i < bytes.length; i++) {
                if (bytes[i] > 127) {
                    if (this.fatal) {
                        throw new TypeError('Invalid ASCII character');
                    }
                    str += '\uFFFD';
                } else {
                    str += String.fromCharCode(bytes[i]);
                }
            }
            return str;
        },

        _decodeISO88591: function(bytes) {
            let str = '';
            for (let i = 0; i < bytes.length; i++) {
                str += String.fromCharCode(bytes[i]);
            }
            return str;
        }
    };

    // 挂载到window
    window.TextEncoder = TextEncoder;
    window.TextDecoder = TextDecoder;
})();
