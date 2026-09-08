# Rules - Phased In Natural Language

## 1. Chapter 1

### Instruction Set

A=B's instruction set includes:

```text
string1=string2
#Find the left most occurrence of string1 in the string, and replace it with string2.
```

### Program Structure

An A=B program consists of several lines of instructions. Each line must include exactly one equal sign, or be a blank line.

### Execution Order

1. Read the input string.
2. Starting by the topmost line, find the first line that can be executed.
3. If found: execute that line, go to step 2.
4. If none is found: return current string as output.

### Other

`#` stands for comment. The first `#` in each line and all characters after it are ignored.

Non-ASCII characters may only be used as commentary.

--

## 2. Chapter 2

### Instruction Set

A=B's instruction set includes:

```text
string1=string2
#Find the left most occurrence of string1 in the string, and replace it with string2.

string1=(return)string2
#If string1 is found, end the program immediately, and replace the entire string with string2.
```

### Program Structure

An A=B program consists of several lines of instructions. Each line must include exactly one equal sign, or be a blank line.

**Following characters are reserved: =()#**

**Brackets must occur at the start of left or right string, in pairs. Keyword is placed in the middle.**

### Execution Order

1. Read the input string.
2. Starting by the topmost line, find the first line that can be executed.
3. If found: execute that line, go to step 2.
4. If none is found: return current string as output.

### Other

`#` stands for comment. The first `#` in each line and all characters after it are ignored.

Non-ASCII characters may only be used as commentary.

--

## 3. Chapter 3

### Instruction Set

A=B's instruction set includes:

```text
string1=string2
#Find the left most occurrence of string1 in the string, and replace it with string2.

string1=(return)string2
#If string1 is found, end the program immediately, and replace the entire string with string2.

(start)string1=string2
(end)string1=string2
#If string1 is at the start / end of string, replace it with string2.

string1=(start)string2
string1=(end)string2
#Find the left most occurrence of string1 in the string, remove it and add string2 to start / end of string.
```

### Program Structure

An A=B program consists of several lines of instructions. Each line must include exactly one equal sign, or be a blank line.

Following characters are reserved: =()#

Brackets must occur at the start of left or right string, in pairs. Keyword is placed in the middle.

**Each side may contain up to one keyword.**

**For example, (start)a=(end)b is valid.**

### Execution Order

1. Read the input string.
2. Starting by the topmost line, find the first line that can be executed.
3. If found: execute that line, go to step 2.
4. If none is found: return current string as output.

### Other

`#` stands for comment. The first `#` in each line and all characters after it are ignored.

Non-ASCII characters may only be used as commentary.

--

## 4. Chapter 4

### Instruction Set

A=B's instruction set includes:

```text
string1=string2
#Find the left most occurrence of string1 in the string, and replace it with string2.

string1=(return)string2
#If string1 is found, end the program immediately, and replace the entire string with string2.

(start)string1=string2
(end)string1=string2
#If string1 is at the start / end of string, replace it with string2.

string1=(start)string2
string1=(end)string2
#Find the left most occurrence of string1 in the string, remove it and add string2 to start / end of string.

(once)string1=string2
#Ignore this instruction after its first execution.
```

### Program Structure

An A=B program consists of several lines of instructions. Each line must include exactly one equal sign, or be a blank line.

Following characters are reserved: =()#

Brackets must occur at the start of left or right string, in pairs. Keyword is placed in the middle.

Each side may contain up to one keyword.

For example, (start)a=(end)b is valid.

### Execution Order

1. Read the input string.
2. Starting by the topmost line, find the first line that can be executed.
3. If found: execute that line, go to step 2.
4. If none is found: return current string as output.

### Other

`#` stands for comment. The first `#` in each line and all characters after it are ignored.

Non-ASCII characters may only be used as commentary.

--

## 5. Chapter 5

### Instruction Set

A=B's instruction set includes:

```text
string1=string2
#Find the left most occurrence of string1 in the string, and replace it with string2.

string1=(return)string2
#If string1 is found, end the program immediately, and replace the entire string with string2.

(start)string1=string2
(end)string1=string2
#If string1 is at the start / end of string, replace it with string2.

string1=(start)string2
string1=(end)string2
#Find the left most occurrence of string1 in the string, remove it and add string2 to start / end of string.

(once)string1=string2
#Ignore this instruction after its first execution.
```

### Program Structure

An A=B program consists of several lines of instructions. Each line must include exactly one equal sign, or be a blank line.

Following characters are reserved: =()#

Brackets must occur at the start of left or right string, in pairs. Keyword is placed in the middle.

Each side may contain up to one keyword.

For example, (start)a=(end)b is valid.

### Execution Order

1. Read the input string.
2. Starting by the topmost line, find the first line that can be executed.
3. If found: execute that line, go to step 2.
4. If none is found: return current string as output.

### Other

`#` stands for comment. The first `#` in each line and all characters after it are ignored.

Non-ASCII characters may only be used as commentary.

--

## 6. Chapter 6

### Instruction Set

A=B's instruction set includes:

```text
string1=string2
#Find the left most occurrence of string1 in the string, and replace it with string2.
```

### Program Structure

An A=B program consists of several lines of instructions. Each line must include exactly one equal sign, or be a blank line.

Following characters are reserved: =#

### Execution Order

1. Read the input string.
2. Starting by the topmost line, find the first line that can be executed.
3. If found: execute that line, go to step 2.
4. If none is found: return current string as output.

### Other

`#` stands for comment. The first `#` in each line and all characters after it are ignored.

Non-ASCII characters may only be used as commentary.