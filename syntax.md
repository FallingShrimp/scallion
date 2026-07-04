# Scallion 语法规范

## 基本规则

- **大小写敏感**：关键字必须小写。
- **换行敏感**：每条语句通常独占一行；`select` 与 `jump` 的映射块使用多行 `{}` 结构。
- **空白**：行首的空格和制表符会被忽略；同一行内的连续空白保留在文本中。

## 标识符

```plain
ID = [a-zA-Z_] \w* \??
```

- 以字母或下划线开头。
- 后可跟字母、数字、下划线。
- 允许以单个 `?` 结尾（常用于变量名，如 `eat?`）。

## 注释

```plain
// 注释内容
```

- 双斜杠到行尾的内容会被解析器忽略。

## 标题

```plain
*标题文本
```

- 以星号 `*` 开头，后跟任意文本直到行尾。
- 一个剧本建议只包含一个标题，通常置于文件最开头。
- 例：`*day start`

## 标签（Label）

```plain
标签名#语句
```

- 在任意语句前可附加标签，以 `#` 分隔。
- 标签用于为语句命名，供 `jump` 作为跳转目标。
- 标签本身不包含 `#` 后的空格。
- 特例：若写成 `标签名#` 且后面没有内容，则等价于 `exit`。
- 例：

  ```plain
  eaten#talk 你好Tera！我已经吃饭了。
  e#exit
  ```

## 语句

### enter — 角色登场

```plain
enter Character:Emotion
```

- 声明一个角色进入场景，并指定其心情/表情。
- `Character` 和 `Emotion` 均为标识符。
- 例：`enter Tera:a`

### focus — 聚焦角色

```plain
focus 角色名
```

- 将镜头/对话焦点切换到指定角色。
- 例：`focus Tera`

### unfocus — 取消聚焦

```plain
unfocus 角色名
```

- 取消对指定角色的聚焦。
- 例：`unfocus Tera`

### talk — 对话

```plain
talk  文本   // 等待点击后推进
talk& 文本   // 自动推进
```

- `talk` 后的文本从第一个非空白字符开始，一直采集到行尾。
- `talk`：玩家需要点击才能进入下一句。
- `talk&`：文本/动画播放完毕后自动进入下一句，常用于 `select` 选择后的自动对话。
- 例：

  ```plain
  talk 你好Pico，你吃饭了吗？？？
  talk& （自动播放下一句）
  ```

### play — 播放资源

```plain
play  资源   // 播放后继续（fire and forget）
play& 资源   // 等待播放完毕后继续（await）
```

- `play` 用于播放音效、图片、视频等资源。
- `play`：启动资源后不阻塞剧本流程。
- `play&`：等待该资源播放完毕才执行下一条语句。
- 资源名从第一个非空白字符采集到行尾。
- 例：

  ```plain
  play& pico-eating.png
  play pico-eaten.mp4
  play pico-uneaten.wav
  ```

### select — 分支选择

```plain
select {
    选项1
    选项2
    ...
} -> VariableName
```

- 向玩家展示一组选项。
- 每个选项独占一行，行内所有内容（除换行外）构成选项文本。
- `->` 后面跟一个标识符（VariableName），用于存储玩家的选择结果。
- 选择结果以 **0-based 整数索引** 存入变量，供后续 `jump` 使用。
- 例：

  ```plain
  select {
      Pico吃饭了
      Pico没吃饭
  } -> eat?
  ```

### jump — 跳转

#### 无条件跳转

```plain
jump 标签名
```

- 直接跳转到指定标签所在语句。
- 例：`jump e`

#### 条件跳转

```plain
jump 变量名 {
    整数值:标签名
    整数值:标签名
    ...
}
```

- 根据 `变量名` 中存储的值，在映射表中查找对应的标签并跳转。
- 映射块每行一条，格式为 `整数:标签名`。
- 例：

  ```plain
  jump eat? {
      0:eaten
      1:uneaten
  }
  ```

### exit — 终止

```plain
exit
```

- 表示剧本结束。
- 例：`e#exit`

## 完整示例

```plain
*day start

enter Tera:a
enter Pico:b

focus Tera
talk& 你好Pico，你吃饭了吗？？？

select {
    Pico吃饭了
    Pico没吃饭
} -> eat?

unfocus Tera
focus Pico

jump eat? {
    0:eaten
    1:uneaten
}

// --- 已吃饭分支 ---
eaten#talk 你好Tera！我已经吃饭了。
play& pico-eating.png
play pico-eaten.mp4
jump e

// --- 没吃饭分支 ---
uneaten#talk 你好Tera！我还没吃饭。
play pico-uneaten.wav
jump e

// --- 结束 ---
e#exit
```
