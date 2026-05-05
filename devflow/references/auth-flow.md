---
name: auth-flow
title: 认证授权流程模式
description: 基于 OWASP 和 OAuth2/OIDC RFC 标准的认证授权设计模式
tags: [authentication, authorization, security]
version: "1.0"
applicable_stages: [solution_design]
priority: 3
---

## 概述

认证（Authentication）与授权（Authorization）是系统安全的基石。本参考基于 OWASP Authentication Cheat Sheet、RFC 6749 (OAuth 2.0)、RFC 7636 (PKCE)、RFC 7519 (JWT) 等公开标准，定义常见认证授权模式及其适用场景。

## 认证模式

### Session-Cookie

服务端维护会话状态，通过 Set-Cookie 下发 Session ID。

- **适用场景**: 传统服务端渲染应用（SSR）
- **安全要点**: Cookie 设置 HttpOnly + Secure + SameSite=Strict；Session ID 使用加密随机数（≥128 bit）；服务端校验 IP/UA 指纹

### JWT (JSON Web Token)

无状态令牌，包含签名的 Claims。

- **适用场景**: 微服务间认证、无状态 API
- **安全要点**: 签名算法使用 RS256/ES256（非对称）；Access Token 短有效期（≤15min）；Refresh Token 存储于 HttpOnly Cookie；禁止在 Payload 中存放敏感信息；验证 iss/aud/exp 声明

### OAuth 2.0 + OIDC

委托授权协议，OIDC 在 OAuth 2.0 之上增加身份层。

- **适用场景**: 第三方登录、SSO、B2B 集成
- **授权模式选择**:
  - 公共客户端（SPA/移动端）: Authorization Code + PKCE
  - 机密客户端（服务端）: Authorization Code + Client Secret
  - 服务间通信: Client Credentials
  - 禁止使用 Implicit Grant 和 Resource Owner Password Credentials

### API Key

静态密钥通过 Header 传递（`X-API-Key`）。

- **适用场景**: 服务间简单认证、开发者 API
- **安全要点**: Key 随机生成（≥256 bit）；支持 Key 轮换与撤销；绑定 IP 白名单或 Scope

### mTLS (Mutual TLS)

双向 TLS 证书认证。

- **适用场景**: 零信任网络、服务网格（Service Mesh）
- **安全要点**: 证书由内部 CA 签发；短有效期自动轮换；证书与身份绑定

## 授权模式

| 模式 | 全称 | 适用场景 |
|---|---|---|
| RBAC | Role-Based Access Control | 角色固定、权限粒度粗 |
| ABAC | Attribute-Based Access Control | 动态策略、上下文敏感 |
| ReBAC | Relationship-Based Access Control | 社交图谱、资源从属关系 |
| ACL | Access Control List | 资源级细粒度控制 |

推荐优先级：RBAC（简单场景）→ ReBAC（关系型场景）→ ABAC（复杂策略场景）。

## 安全最佳实践

- 密码存储使用 bcrypt（cost ≥ 12）或 argon2id
- 登录失败 Rate Limiting：同 IP ≤ 5 次/分钟
- 启用 CSRF Token（Session-Cookie 模式）
- Token 存储优先级：HttpOnly Cookie > SessionStorage > 内存 > LocalStorage（最不安全）
- 敏感操作要求重新认证（Step-Up Authentication）
- 审计日志记录所有认证与授权事件

## Agent 使用指引

1. **模式选择**: 根据项目类型（SSR/SPA/微服务/B2B）推荐合适的认证与授权模式组合。
2. **安全合规检查**: 审查代码中的认证实现，检测常见漏洞（JWT 无签名验证、硬编码密钥、缺少 Rate Limiting 等）。
3. **配置生成**: 生成 OAuth 2.0/OIDC 的标准配置（授权 URL、Token URL、Scope 定义）。
4. **威胁建模**: 识别认证授权流程中的攻击面，输出 STRIDE 威胁清单。
