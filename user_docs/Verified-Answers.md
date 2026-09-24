# Verified Answers

English | [简体中文](Verified-Answers-zh-CN.md)

## 1-1 A to B (c1_1_atob)
**Input:** A string of "a", "b" and "c".
**Output:** Replace each "a" with "b".
**Constraint:** 1 &lt;= Input length &lt;= 7
```
a=b
```

## 1-2 Uppercase (c1_2_uppercase)
**Input:** A string of "a", "b" and "c".
**Output:** Replace each letter with its uppercase.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
a=A
b=B
c=C
```

## 1-3 Singleton (c1_3_singleton)
**Input:** A string of "a", "b" and "c".
**Output:** Replace consecutive repeated letters with a single letter.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
aa=a
bb=b
cc=c
```

## 1-4 Singleton 2 (c1_4_singleton2)
**Input:** A string of "a", "b" and "c".
**Output:** Remove consecutive "a"s.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
aaa=aa
aa=
```

## 1-5 Sort (c1_5_sort)
**Input:** A string of "a", "b" and "c".
**Output:** Sort the input in alphabetical order.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
ba=ab
ca=ac
cb=bc
```

## 1-6 Compare (c1_6_compare)
**Input:** A string of "a" and "b".
**Output:** The most common letter.
**Constraint:** 1 &lt;= Input length &lt;= 11
**The number of "a"s and "b"s is different.**
```
ab=
ba=
aa=a
bb=b
```

## 2-1 Hello World (c2_1_hello)
**Input:** A string of a, b and c.
**Output:** helloworld
**Constraint:** 1 &lt;= Input length &lt;= 7
```
=(return)helloworld
```

## 2-2 AAA (c2_2_aaa)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if the input contains at least three "a"s.
Otherwise, return false.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
b=
c=
aaa=(return)true
=(return)false
```

## 2-3 Exactly Three (c2_3_exactly)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if the input contains exactly three letters.
Otherwise, return false.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
b=a
c=a
aaaa=(return)false
aaa=(return)true
=(return)false
```

## 2-4 Remainder (c2_4_remainder)
**Input:** A string of a, b and c.
**Output:** Divide the input length by 3. Output the remainder.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
b=a
c=a
aaaa=a
aaa=0
aa=2
a=1
```

## 2-5 Odd (c2_5_odd)
**Input:** A string of a, b and c.
**Output:** Return true if the amount of each letter is either an odd value, or zero.
Otherwise, return false.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
ba=ab
ca=ac
cb=bc
aaa=a
bbb=b
ccc=c
aa=(return)false
bb=(return)false
cc=(return)false
=(return)true
```

## 2-6 The Only (c2_6_only)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if exactly one letter is different from adjacent letters.
Otherwise, return false.
For example, in string "babbcc", first a, and first b are different from neighbours. Thus return false.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
aaa=aa
aa=|
a=@
bbb=bb
bb=|
b=@
ccc=cc
cc=|
c=@
|=
@@=(return)false
@=(return)true
=(return)false
```

## 2-7 Ascend (c2_7_ascend)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if "c" is more than "b", and "b" is more than "a".
Otherwise, return false.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
ba=ab
ca=ac
cb=bc
b|=|b
bc=|
a|=
|c=(return)true
=(return)false
```

## 2-8 Most (c2_8_most)
**Input:** A string of "a", "b" and "c".
**Output:** Return the most common letter.
**Constraint:** 1 &lt;= Input length &lt;= 7
**There's no ties for the most.**
```
ba=ab
ca=ac
cb=bc
aaaa=(return)a
bbbb=(return)b
cccc=(return)c
=abc
```

## 2-9 Least (c2_9_least)
**Input:** A string of "a", "b" and "c".
**Output:** Return the least common letter.
**Constraint:** 2 &lt;= Input length &lt;= 7
**There's no ties for the least.**
```
ba=ab
ca=ac
cb=bc
abc=(return)b
aab=(return)c
bc=(return)a
=ab
```

## 3-1 Remove (c3_1_Remove)
**Input:** A string of "a", "b" and "c".
**Output:** Remove all "a"s at the start and end of input string.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(start)a=
(end)a=
```

## 3-2 Spin (c3_2_spin)
**Input:** A string of "a", "b" and "c".
**Output:** Move each letter before the first "a" to the end of string.
**Constraint:** 1 &lt;= Input length &lt;= 7
**Input contains at least one "a".**
```
(start)b=(end)b
(start)c=(end)c
```

## 3-3 A to B 2 (c3_3_atob2)
**Input:** A string of "a", "b" and "c".
**Output:** Replace all "a"s at the start and the end of string with "b"s.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(start)a=(end)|
|=(start)b
(end)a=(start)@
@=(end)b
```

## 3-4 Swap (c3_4_swap)
**Input:** A string of "a", "b" and "c".
**Output:** Swap all "a"s at the start and all "b"s at the end of string.
**Constraint:** 2 &lt;= Input length &lt;= 8
**Input always starts with "a" and ends with "b".**
```
(end)b=(start)|b
|ba=(end)|ab
|=
```

## 3-5 Match (c3_5_match)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if the input string starts and ends with same letter.
Otherwise, return false.
**Constraint:** 2 &lt;= Input length &lt;= 7
```
(end)a|=(return)true
(end)b@=(return)true
(end)c$=(return)true
(start)a=(end)|
(start)b=(end)@
(start)c=(end)$
=(return)false
```

## 3-6 Most 2 (c3_6_most2)
**Input:** A string of "a", "b" and "c".
**Output:** Keep the most common letters and delete the rest.
**Constraint:** 1 &lt;= Input length &lt;= 7
**There's no ties for the most.**
```
ab=(end)|c
ba=(end)|c
ca=ac
cb=bc
c|c=(end)|
ac=(end)|
bc=(end)|
a|=aa
b|=bb
|=c
```

## 3-7 Palindrome (c3_7_palindrome)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if input string is a palindrome. (reads the same backward as forward)
Otherwise, return false.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
a|a@=
b|b@=
c|c@=
(start)a=(end)|a@
(start)b=(end)|b@
(start)c=(end)|c@
@|=(return)false
=(return)true
```

## 4-1 Hello 2 (c4_1_hello2)
**Input:** A string of "a", "b" and "c".
**Output:** Add "hello" to the start of string.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)=(start)hello
```

## 4-2 Remove 2 (c4_2_remove2)
**Input:** A string of "a", "b" and "c".
**Output:** Remove the first three "a"s. (Remove all "a"s if less than three.)
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)a=
(once)a=
(once)a=
```

## 4-3 Cut (c4_3_cut)
**Input:** A string of "a", "b" and "c".
**Output:** Remove the first three letters.
**Constraint:** 3 &lt;= Input length &lt;= 7
```
(once)=(start)|||
|a=
|b=
|c=
```

## 4-4 Remove 3 (c4_4_remove3)
**Input:** A string of "a", "b" and "c".
**Output:** Remove last three "a"s. (Remove all "a"s if less than three.)
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)=(end)|||
a|=
b|=|b
c|=|c
|=
```

## 4-5 Reverse (c4_5_reverse)
**Input:** A string of "a", "b" and "c".
**Output:** Swap first letter and last letter.
**Constraint:** 2 &lt;= Input length &lt;= 7
```
(once)=(start)|
|a=(end)@a
|b=(end)@b
|c=(end)@c
a@=(start)a
b@=(start)b
c@=(start)c
```

## 4-6 Reverse 2 (c4_6_reverse2)
**Input:** A string of "a", "b" and "c".
**Output:** Reverse input.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)=(start)|||||||
|a=(start)a
|b=(start)b
|c=(start)c
|=
```

## 4-7 Cut 2 (c4_7_cut2)
**Input:** A string of "a", "b" and "c".
**Output:** Remove the third letter.
**Constraint:** 3 &lt;= Input length &lt;= 7
```
(once)=||||||||||||
|b=a
|c=b
||||a=c|||
||=|
|a=
```

## 4-8 Clone (c4_8_clone)
**Input:** A string of "a", "b" and "c".
**Output:** Copy first three letters of the string, and add them to the end of string.
**Constraint:** 3 &lt;= Input length &lt;= 7
```
(once)=|||
@a=(start)a
@b=(start)b
@c=(start)c
|a=(end)@aa
|b=(end)@bb
|c=(end)@cc
(once)=@@@
```

## 4-9 A to B 3 (c4_9_atob3)
**Input:** A string of "a", "b" and "c".
**Output:** Replace each "a" with "b".
Replace each "b" with "a".
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)=(start)|
|a=b|
|b=a|
|c=c|
|=
```

## 4-10 Half (c4_10_odd2)
**Input:** A string of "a", "b" and "c".
**Output:** Remove each letter at an odd position. (1st, 3rd, 5th, and 7th letter)
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)=(start)||
||a=|
||b=|
||c=|
|a=a||
|b=b||
|c=c||
|=
```

## 4-11 Clone 2 (c4_11_clone2)
**Input:** A string of "a", "b" and "c".
**Output:** Repeat the input string.
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)=(end)|
@a=(end)a
@b=(end)b
@c=(end)c
a|=|@|aa
b|=|@|bb
c|=|@|cc
|=
```

## 4-12 To B or not to B (c4_12_tob)
**Input:** A string of "a", "b" and "c".
**Output:** If at least one "b" occurs, replace each "a" with "b".
Otherwise, replace each "a" with "c".
**Constraint:** 1 &lt;= Input length &lt;= 7
```
(once)b=a|b
b|=|b
c|b=|bc
a|=(end)|b
|b=
a=c
```

## 4-13 Center (c4_13_center)
**Input:** A string of "a", "b" and "c".
**Output:** Return the letter in the center.
**Constraint:** 1 &lt;= Input length &lt;= 7
Input length is odd.
```
(once)=(start)||||||||||||||||||||||||||||||||||||||||||||||||||||
|a=(end)a
|b=(end)b
|c=(end)c
(start)a=(return)a
(start)b=(return)b
(start)c=(return)c
```

## 4-14 Center 2 (c4_14_center2)
**Input:** A string of "a", "b" and "c".
**Output:** Delete the letter in the center.
**Constraint:** 1 &lt;= Input length &lt;= 7
Input length is odd.
```
(once)=@|$||
||a=(end)|@aa
||b=(end)|@bb
||c=(end)|@cc
$|=(start)|
$=$||$||
|@a=
|@b=
|@c=
```

## 4-15 Expansion (c4_15_expansion)
**Input:** A string of "a", "b" and "c".
**Output:** Repeat the xth letter x times.
**Constraint:** 1 &lt;= Input length &lt;= 6
```
(once)=||@||@
||@a=(end)|@|a|@|
||@b=(end)|@|b|@|
||@c=(end)|@|c|@|
a|@||@|b|@||@|c=(start)|||@|@
@||@|a=|@||@||@abcaa
@||@|b=|@||@||@abcbb
@||@|c=|@||@||@abccc
|@|=
```

## 4-16 Merge (c4_16_merge)
**Input:** Two strings of "a" and "b", separated by a ",".
**Output:** Merge the two strings.
Letters from first string and second string alternates in the output string.
**Constraint:** 1 &lt;= String length &lt;= 5
**Both strings are of same length.**
```
>,,,a=(end)a
>,,,b=(end)b
,>=(start)>,,,
>,,,,,=
,=,>,,
```

## 5-1 Count (c5_1_count)
**Input:** A binary number.
**Output:** That many "a"s.
**Constraint:** 1 &lt;= Input number &lt;= 63
```
a1=1aa
a0=1a
1=a
```

## 5-2 A+1 (c5_2_plus)
**Input:** A binary numbers.
**Output:** Input plus 1.
**Constraint:** 1 &lt;= Input number &lt;= 1023
```
(once)=(end)|
1|=|0
0|=1
|=1
```

## 5-3 A+B (c5_3_plus2)
**Input:** Two binary numbers, separated by a "+".
**Output:** Their sum.
**Constraint:** 1 &lt;= Input number &lt;= 31
```
(once)+1=|+
+1=1++
+0=1+
|1=|+
+=@
|=
1@=@0
0@=1
(start)@=(start)1
```

## 5-4 A-B (c5_4_minus)
**Input:** Two binary numbers, separated by a "-".
**Output:** Their difference.
**Constraint:** 1 &lt;= Input number &lt;= 31
**First number &gt; Second number**
```
-1=-|
|1=1||
|0=1|
-|=@-
0@=@1
(start)1@=(start)
1@=0
-=
```

## 5-5 A*B (c5_5_multiply)
**Input:** Two binary numbers, separated by a "*".
**Output:** Their product.
**Constraint:** 1 &lt;= Input number &lt;= 31
```
@^=^@
%^=^%
&^=+&
1+=+0
0+=1
(start)+=(start)1
@%=%@^
(once)1=(start)0&|@
@1=1@@
@0=1@
|1=|@
|=
(once)*1=$%
%1=1%%
%0=1%
$1=$%
$=
%=
@=
&=
```

## 5-6 A/B (c5_6_div)
**Input:** Two binary numbers, separated by a "/".
**Output:** Their quotient and remainder, separated by a ",".
**Constraint:** 1 &lt;= Input number &lt;= 31
```
(once)1=|@
@1=1@@
@0=1@
|1=|@
|=
(once)/1=/$
$1=1$$
$0=1$
/1=/$
(once)=(end)%
(start)/=(start)^
(start)&>=(start)^
>/=/$
/$=&>
>&=&>
@&=*
*>=>*
*$=&>
*%=/%+
>=@
$=
^=
%+=+%
@+=+@
@%=%@
(once)=(start)0-
-+=_-
1_=_0
0_=1
(start)_=(start)1
-=
%=,0<
<@=_<
,_=,1
<=
```

## 6-1 Hello Again (c6_1_hello3)
**Input:** A string of "a", "b" and "c".
**Output:** helloworld
**Constraint:** 1 &lt;= Input length &lt;= 7
**You may not use keywords in this level.**
```
b=a
c=a
aa=a
a=helloworld
```

## 6-2 Palindrome 2 (c6_2_palindrome2)
**Input:** A string of "a", "b" and "c".
**Output:** Return true if input string is a palindrome. (reads the same backward as forward)
Otherwise, return false.
**Constraint:** 2 &lt;= Input length &lt;= 7
**You may not use keywords in this level.**
```
b=|a|
c=||a||
a@=@a
|@=@|
$a=a$
$|=|$
%a=a%
%|=|%
a$=
|%=
@$=true
@%=true
$=^
%=^
a^=^
|^=^
@^=false
@a=@$
@|=@%
@=true
|=|@
aa=a@a
```

## 6-3 To B or not to B 2 (c6_3_tob2)
**Input:** A string of "a", "b" and "c".
**Output:** If at least one "b" occurs, replace each "a" with "b".
Otherwise, replace each "a" with "c".
**Constraint:** 1 &lt;= Input length &lt;= 7
**You may not use keywords in this level.**
```
ba=bb
ab=bb
bca=bcb
acb=bcb
bcca=bccb
accb=bccb
bccca=bcccb
acccb=bcccb
bcccca=bccccb
accccb=bccccb
bccccca=bcccccb
acccccb=bcccccb
a=c
```

