import pandas as pd

breast_a_file = 'data/breast_a.csv'
breast_b_file = 'data/breast_b.csv' # with label

length = 1000
offset = 100

df_a = pd.read_csv(breast_a_file)
df_b = pd.read_csv(breast_b_file)

#df_a.iloc[:length].to_csv('data/host_demo_a.csv', index=False)
#df_a.iloc[length:2*length].to_csv('data/host_demo_b.csv', index=False)
#df_b.iloc[length//2:length*3//2, :4].to_csv('data/guest_demo.csv', index=False)

df_b.iloc[offset:length+offset,:4].to_csv('data/guest_demo.csv', index=False)
print('guest_demo shape:', df_b.iloc[offset:length+offset,:4].shape)
start = 0
end = length + offset
for i in range(1, 4):
    csv_len = offset * i
    df_a.iloc[:csv_len].to_csv('data/host_demo_a_v%d.csv' % i, index=False)
    df_a.iloc[end-csv_len:end].to_csv('data/host_demo_b_v%d.csv' % i, index = False)
    print('host a v%d' % i, df_a.iloc[:csv_len].shape)
    print('host b v%d' % i, df_a.iloc[end-csv_len:end].shape) 
