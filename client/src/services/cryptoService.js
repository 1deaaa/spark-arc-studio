/**
 * 前端加密服务
 * 使用 RSA-OAEP 加密敏感数据，与后端的 crypto.py 对接
 */

let cachedPublicKey = null;
let publicKeyPem = null;

/**
 * 获取服务器公钥
 */
export async function getPublicKey() {
  if (cachedPublicKey) {
    return cachedPublicKey;
  }

  try {
    const response = await fetch('/api/crypto/public-key');
    if (!response.ok) {
      throw new Error('获取公钥失败');
    }
    const data = await response.json();
    publicKeyPem = data.public_key;

    // 将 PEM 格式的公钥转换为 CryptoKey
    cachedPublicKey = await importPublicKey(publicKeyPem);
    return cachedPublicKey;
  } catch (error) {
    console.error('获取公钥失败:', error);
    throw error;
  }
}

/**
 * 将 PEM 格式的公钥转换为 CryptoKey
 */
async function importPublicKey(pem) {
  // 移除 PEM 头尾和换行符
  const pemHeader = '-----BEGIN PUBLIC KEY-----';
  const pemFooter = '-----END PUBLIC KEY-----';
  const pemContents = pem
    .replace(pemHeader, '')
    .replace(pemFooter, '')
    .replace(/\s/g, '');

  // Base64 解码
  const binaryDer = atob(pemContents);
  const binaryArray = new Uint8Array(binaryDer.length);
  for (let i = 0; i < binaryDer.length; i++) {
    binaryArray[i] = binaryDer.charCodeAt(i);
  }

  // 导入公钥
  return await window.crypto.subtle.importKey(
    'spki',
    binaryArray,
    {
      name: 'RSA-OAEP',
      hash: 'SHA-256',
    },
    true,
    ['encrypt']
  );
}

/**
 * 使用 RSA 公钥加密数据
 * @param {string} plaintext - 要加密的明文
 * @returns {string} 加密后的 Base64 字符串，带有 "ENC:" 前缀
 */
export async function encryptData(plaintext) {
  if (!plaintext) return plaintext;

  try {
    const publicKey = await getPublicKey();
    
    // 将明文转换为 Uint8Array
    const encoder = new TextEncoder();
    const data = encoder.encode(plaintext);

    // RSA-OAEP 加密
    const encrypted = await window.crypto.subtle.encrypt(
      {
        name: 'RSA-OAEP',
      },
      publicKey,
      data
    );

    // 转换为 Base64
    const encryptedArray = new Uint8Array(encrypted);
    let binary = '';
    for (let i = 0; i < encryptedArray.length; i++) {
      binary += String.fromCharCode(encryptedArray[i]);
    }
    const base64 = btoa(binary);

    // 返回带前缀的加密数据
    return 'ENC:' + base64;
  } catch (error) {
    console.error('加密失败:', error);
    throw new Error('数据加密失败');
  }
}

/**
 * 加密密码（用于登录/注册）
 */
export async function encryptPassword(password) {
  return await encryptData(password);
}

/**
 * 加密 API Key
 */
export async function encryptApiKey(apiKey) {
  return await encryptData(apiKey);
}

/**
 * 加密 Session Token
 */
export async function encryptToken(token) {
  return await encryptData(token);
}

/**
 * 清除缓存的公钥（当服务器重启时需要调用）
 */
export function clearPublicKeyCache() {
  cachedPublicKey = null;
  publicKeyPem = null;
}