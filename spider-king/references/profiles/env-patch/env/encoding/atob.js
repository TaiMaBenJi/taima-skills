/**
 * @env-module atob/btoa
 * @description Base64编解码函数模拟
 * @compatibility Chrome 80+, Firefox 75+, Edge 79+
 */

(function() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';

    function invalidCharacter(message) {
        if (typeof DOMException === 'function') {
            return new DOMException(message, 'InvalidCharacterError');
        }
        const error = new TypeError(message);
        error.name = 'InvalidCharacterError';
        return error;
    }

    // btoa - 字符串转Base64
    function btoa(str) {
        if (typeof str !== 'string') {
            str = String(str);
        }
        
        // 检查是否包含非Latin1字符
        for (let i = 0; i < str.length; i++) {
            if (str.charCodeAt(i) > 255) {
                throw invalidCharacter(
                    "Failed to execute 'btoa' on 'Window': The string to be encoded contains characters outside of the Latin1 range."
                );
            }
        }
        
        let output = '';
        let i = 0;
        
        while (i < str.length) {
            const chr1 = str.charCodeAt(i++);
            const chr2 = str.charCodeAt(i++);
            const chr3 = str.charCodeAt(i++);
            
            const enc1 = chr1 >> 2;
            const enc2 = ((chr1 & 3) << 4) | (chr2 >> 4);
            let enc3 = ((chr2 & 15) << 2) | (chr3 >> 6);
            let enc4 = chr3 & 63;
            
            if (isNaN(chr2)) {
                enc3 = enc4 = 64;
            } else if (isNaN(chr3)) {
                enc4 = 64;
            }
            
            output += chars.charAt(enc1) + chars.charAt(enc2) + chars.charAt(enc3) + chars.charAt(enc4);
        }
        
        return output;
    }

    // atob - Base64转字符串
    function atob(str) {
        if (typeof str !== 'string') {
            str = String(str);
        }
        
        // 去除空白字符
        str = str.replace(/\s/g, '');
        
        // 检查是否是有效的Base64字符串
        if (!/^[A-Za-z0-9+\/]*={0,2}$/.test(str)) {
            throw invalidCharacter(
                "Failed to execute 'atob' on 'Window': The string to be decoded is not correctly encoded."
            );
        }
        
        // 补齐padding
        while (str.length % 4) {
            str += '=';
        }
        
        let output = '';
        let i = 0;
        
        while (i < str.length) {
            const enc1 = chars.indexOf(str.charAt(i++));
            const enc2 = chars.indexOf(str.charAt(i++));
            const enc3 = chars.indexOf(str.charAt(i++));
            const enc4 = chars.indexOf(str.charAt(i++));
            
            const chr1 = (enc1 << 2) | (enc2 >> 4);
            const chr2 = ((enc2 & 15) << 4) | (enc3 >> 2);
            const chr3 = ((enc3 & 3) << 6) | enc4;
            
            output += String.fromCharCode(chr1);
            
            if (enc3 !== 64) {
                output += String.fromCharCode(chr2);
            }
            if (enc4 !== 64) {
                output += String.fromCharCode(chr3);
            }
        }
        
        return output;
    }

    // 挂载到window
    window.btoa = btoa;
    window.atob = atob;
})();
