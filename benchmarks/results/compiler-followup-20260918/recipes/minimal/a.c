__attribute__((noinline)) static int local(int x) {return x>8?x*3:x+2;}
int wrap(int x){return local(x);}
