extern int wrap(int); int main(void){volatile int s=0;for(int i=0;i<10000;i++)s+=wrap(i);return s==0;}
